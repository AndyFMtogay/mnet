# 项目部署
整套服务项目部署流程，整套操作都在deploy目录下进行。

# docker跨主机通信
现有机器vm1（192.168.71.148）和vm2（192.168.71.152）。设vm1为管理主节点，其余为工作节点。

跨主机
```
在 148 上创建manager
$ docker swarm init --advertise-addr 192.168.71.148

在其余的工作机器加入节点
$ docker swarm join --token SWMTKN-1-5hcor53t93skr6k8sacb54n8sipo1za7oqa4wgywid8ugjhkjd-6giddshlk9dsa5213ay80um8s 192.168.71.148:2377

如果找不到了加入命令，则可以在管理节点输入
$ docker swarm join-token worker
```

网络
```
创建网络，--attachable  是为了swarm集群外的容器能够加入该网络
$ docker network create -d overlay --attachable zxnet

148机器（manager）测试alpine1 
$ docker run -it --name alpine1 --network zxnet alpine

152机器(worker)测试alpine2，注意 -d 表示detached 
$ docker run -it --name alpine2 --network zxnet alpine

互相启动ping命令
$ ping alpine2
```

# Zookeeper
```
$ docker run \
    --name zoo1 \
    --restart always \
    --network zxnet \
    --detach \
    zookeeper:3.5.5 
```

# Kafka
```
$ wget -P ./pkg http://mirrors.tuna.tsinghua.edu.cn/apache/kafka/2.3.0/kafka_2.12-2.3.0.tgz

$ docker build -t java-base -f Dockerfile-java-base .
$ docker build -t kafka -f Dockerfile-kafka .

$ docker run \
    --name kf1 \
    --publish 9092:9092 \
    --link=zoo1:zoo1 \
    --env KAFKA_BROKER_ID=1 \
    --env KAFKA_LISTENERS=PLAINTEXT://:9092 \
    --env KAFKA_ZOOKEEPER_CONNECT=zoo1:2181 \
    --restart always \
    --network zxnet \
    --detach \
    kafka 
```

测试
```
$ docker exec -it kf1 /kafka/kafka_2.12-2.3.0/bin/kafka-topics.sh --create --zookeeper zoo1:2181 --replication-factor 1 --partitions 1 --topic mytest
$ docker exec -it kf1 /kafka/kafka_2.12-2.3.0/bin/kafka-topics.sh --describe --zookeeper zoo1:2181 --topic mytest

$ docker exec -it kf1 /kafka/kafka_2.12-2.3.0/bin/kafka-console-consumer.sh --bootstrap-server kf1:9092 --topic mytest --from-beginning
$ docker exec -it kf1 /kafka/kafka_2.12-2.3.0/bin/kafka-console-producer.sh --broker-list kf1:9092 --topic mytest
```

# Elasticsearch
```
$ docker run \
    --name es1 \
    --publish 9200:9200 \
    --publish 9300:9300 \
    --env "discovery.type=single-node" \
    --restart always \
    --network zxnet \
    --detach \
    elasticsearch:6.4.3
```

# Kibana
```
$ docker run \
    --name kb1 \
    --publish 5601:5601 \
    --link=es1:es1 \
    --env "ELASTICSEARCH_URL=http://es1:9200" \
    --restart always \
    --network zxnet \
    --detach \
    kibana:6.4.3 
```

# Logstash
```
# default.conf定义数据流动，与下方测试紧密关联
$ cp default.conf.example default.conf
$ cp logstash.yml.example logstash.yml

$ docker build -t mylogstash -f Dockerfile-logstash .

$ docker run \
    --name lg1 \
    --publish 4739:4739/udp \
    --publish 21561:21561/udp \
    --publish 21562:21562/udp \
    --link=es1:es1 \
    --restart always \
    --network zxnet \
    --detach \
    mylogstash 
```

测试
```
$ docker logs -f lg1

# es测试
$ python3 logstash_udp_client_test_src.py

# kafka测试 （提前创建好topic）
$ python3 logstash_udp_client_test_dest.py
```