from elasticsearch import Elasticsearch
import json
import jsonpickle
import argparse
import logging
import re
import csv
import datetime
import ipaddress

class index_bucket:

    def __init__(self):
        self.cluster_name = ""
        self.index = ""
        self.indexCnt = 0
        self.total_docs = 0
        self.total_shards = 0
        self.total_bytes = 0
        self.hot_docs = 0
        self.hot_shards = 0
        self.hot_bytes = 0
        self.warm_docs = 0
        self.warm_shards = 0
        self.warm_bytes = 0
        self.cold_docs = 0
        self.cold_shards = 0
        self.cold_bytes = 0
    def __iter__(self):
        return iter([self.cluster_name, self.index, self.indexCnt,
                self.total_docs, self.total_shards, self.total_bytes, 
                self.hot_docs, self.hot_shards, self.hot_bytes, 
                self.warm_docs, self.warm_shards, self.warm_bytes, 
                self.cold_docs, self.cold_shards, self.cold_bytes])




def my_function(node,attribute,hot,warm,cold,user,password,ssl):

    if ssl:
        myscheme = "https"
    else:
        myscheme = "http"    

    if user != "":
        es = Elasticsearch(hosts=[node],
            http_auth=(user, password),
            scheme = myscheme
            )  

    else:
        es = Elasticsearch(hosts=[node])

       

    h2 = es.cluster.health(format="json")




    if h2["status"] != "red":
        nodes = es.cat.nodes( format="json")
        nodeattrs = es.cat.nodeattrs( format="json")


        # build nodetypes dict

        nodetypes = {}

        # populate nodetypes dict
        for nodeattr in nodeattrs:
            if nodeattr["attr"] == attribute:
                nodetypes[nodeattr["node"]] =  nodeattr["value"]


        # get list of all indices from current cluster
        indices = es.cat.indices( format="json",bytes="b",s="index")

        # instatiate new bucket
        bucket = index_bucket()

        # loop through all indices
        for index in indices:

            # convert index into bucketname
            bucket_name = re.sub(r'[0-9]','0', index["index"])

            # do we know this bucket already
            if bucket.cluster_name != h2["cluster_name"] or bucket_name != bucket.index:
                bucket = index_bucket()
                bucket.cluster_name = h2["cluster_name"]
                bucket.index = bucket_name
                all_buckets.append(bucket)

            # sum up the totals
            bucket.total_bytes += int(index["pri.store.size"]) 
            bucket.total_docs += int(index["docs.count"])
            bucket.total_shards += int(index["pri"])

            bucket.indexCnt+=1
            
            # get shards for current index
            shards = es.cat.shards( format="json",bytes="b",index=index["index"])

            for shard in shards:
                if shard["prirep"]=="p":

                    if shard["node"] in nodetypes:
                        nodetype=nodetypes[shard["node"]] 
                        if nodetype == hot:
                            bucket.hot_docs += int(shard["docs"])
                            bucket.hot_bytes += int(shard["store"])
                            bucket.hot_shards += 1
                        if nodetype == warm:
                            bucket.warm_docs += int(shard["docs"])
                            bucket.warm_bytes += int(shard["store"])
                            bucket.warm_shards += 1
                        if nodetype == cold:
                            bucket.cold_docs += int(shard["docs"])
                            bucket.cold_bytes += int(shard["store"])
                            bucket.cold_shards += 1

    remote_clusters = es.remote.info(format="json")
    for remote in remote_clusters:
        remote_cluster = remote_clusters[remote]
        if remote_cluster["connected"]== True:
            ip, separator, port = remote_cluster["seeds"][0].rpartition(':')
            print(ip)
            my_function(ip,attribute,hot,warm,cold,user,password,ssl)

        
if __name__== "__main__":

    parser = argparse.ArgumentParser(description='Generate Elasticsearch stats.')
    parser.add_argument('-n', '--node',
        action="store", dest="node",
        help="node", default="172.17.57.114")
    parser.add_argument('-f', '--format',
        action="store", dest="format",
        help="output format", default="csv")
    parser.add_argument('-a', '--attribute',
        action="store", dest="attribute",
        help="node attribute", default="rack")
    parser.add_argument( '--hot',
        action="store", dest="hot",
        help="node hot attribute", default="hot")
    parser.add_argument( '--warm',
        action="store", dest="warm",
        help="node warm attribute", default="warm")
    parser.add_argument( '--cold',
        action="store", dest="cold",
        help="node cold attribute", default="cold")
    parser.add_argument( '--remote',
        action="store", dest="remote",
        help="remote clusters", default=True)
    parser.add_argument( '--ssl',
        action="store", dest="ssl",
        help="use SSL", default=False)
    parser.add_argument( '--verify_certs',
        action="store", dest="verify_certs",
        help="use SSL", default=False)
    parser.add_argument( '--user',
        action="store", dest="user",
        help="User", default="elastic_stats")
    parser.add_argument( '--password',
        action="store", dest="password",
        help="Password", default="elastic_stats")
    parser.add_argument( '--prefix',
        action="store", dest="prefix",
        help="output prefix", default="elastic-stats-")

    logging.basicConfig(filename='elastic-stats.log', filemode='a',level=logging.DEBUG,format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
    logging.info('start')

    args = parser.parse_args()

    all_buckets = []

    try:
        my_function(args.node,args.attribute,args.hot,args.warm,args.cold,args.user,args.password,args.ssl)

        suffix = '{:%Y%m%d%H%M%S}'.format(datetime.datetime.utcnow())

        if args.format == "json":
            with open(args.prefix+suffix+'.json', 'w') as outfile:
                oneway = jsonpickle.encode(all_buckets, unpicklable=False)
                outfile.write(oneway)
                outfile.close()



        if args.format == "csv":
            with open(args.prefix+suffix+'.csv', mode='w') as csv_file:
                csv_writer = csv.writer(csv_file, lineterminator='\n', delimiter=',', quotechar='"', quoting=csv.QUOTE_NONNUMERIC)

                for bucket in all_buckets:
                    csv_writer.writerow(list(bucket))    
                csv_file.close

    except Exception as err:
        logging.error(err)


    logging.info('stop')
