create database if not exists pnfs_cluster;
GRANT USAGE ON pnfs_cluster . * TO 'pnfs_cluster'@'localhost' IDENTIFIED BY 'TeiPQy6eFf' WITH MAX_QUERIES_PER_HOUR 0 MAX_CONNECTIONS_PER_HOUR 0 MAX_UPDATES_PER_HOUR 0 ;
GRANT SELECT , INSERT , UPDATE , DELETE , CREATE , DROP , INDEX , ALTER , CREATE TEMPORARY TABLES ON `pnfs_cluster` . * TO 'pnfs_cluster'@'localhost'

use pnfs_cluster;

drop table if exists pnc_databases;
create table pnc_databases (
    db_id            int unsigned not null auto_increment,
    shard_id         int unsigned not null,
    role             varchar(10) not null default 'master',
    host             varchar(20) not null,
    port             int(5) not null default 3306,
    db_name          varchar(32) not null,
    username         varchar(32) not null,
    password         varchar(32) not null,
    extra_params     varchar(255) null,
    primary key (db_id)
) TYPE=InnoDB DEFAULT CHARSET=utf8;

alter table pnc_databases add index IDX_DATABASES_SHARD_ID(shard_id);

drop table if exists pnc_shards;
create table pnc_shards (
    shard_id         int unsigned not null auto_increment,
    weight           int(2) not null default 1,
    primary key (shard_id)
) TYPE=InnoDB DEFAULT CHARSET=utf8;

drop table if exists pnc_user_mappings;
create table pnc_user_mappings (
    username         varchar(32) not null,
    shard_id         int unsigned not null,
    primary key (username)
) TYPE=InnoDB DEFAULT CHARSET=utf8;

-- schema for nodes

create database if not exists pnfs_001;
GRANT USAGE ON pnfs_001 . * TO 'pnfs_001'@'localhost' IDENTIFIED BY '7fZOFqQevC' WITH MAX_QUERIES_PER_HOUR 0 MAX_CONNECTIONS_PER_HOUR 0 MAX_UPDATES_PER_HOUR 0 ;
GRANT SELECT , INSERT , UPDATE , DELETE , CREATE , DROP , INDEX , ALTER , CREATE TEMPORARY TABLES ON `pnfs_001` . * TO 'pnfs_001'@'localhost'



use pnfs_001;

drop table if exists pnfs_photo;
create table pnfs_photo (
    username          varchar(32) not null,
    filename          varchar(32) not null,
    secret            varchar(8) not null,
    width             int(5) not null,
    height            int(5) not null,
    file_length       int(11) not null,
    content_type      varchar(15) not null,
    created_time      integer not null,
    sizes             int(5) not null,
    state             tinyint(2) not null,
    primary key (username, filename)
) TYPE=InnoDB DEFAULT CHARSET=utf8;

