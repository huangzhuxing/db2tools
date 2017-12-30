#!/bin/ksh
#################################################################################
## Function: Database Performance Report Tool(DPRT)                             #
## Only support AIX and single instance node now.                               #
##                                                                              #
## Version: 1.0                                                                 #
## Author: huangzhuxing  mail:hzhux@cn.ibm.com                                  #
## Date: 2017-11-08                                                             #
##                                                                              #
## Usage: ./db2performancerpt.ksh <DBNAME>                                      #
##                                                                              #
##                                                                              #
#################################################################################

__VERSION__="1.0" ;
#debug option:
DEBUG_MODE=true ;

#快照保存的目录
SNAPSHOT_DIR=/tmp

#快照保存天数
SAVE_DAYS=+7

#public function
#########################################################################################################
[[ -f ~/sqllib/db2profile ]] && . ~/sqllib/db2profile ;
CACHE_FILE=/tmp/db2alias.`hostname`.`whoami`.cache ;
CACHE_FILE_TMP=${CACHE_FILE}.tmp ;
[[ -f ${CACHE_FILE} ]] && cat ${CACHE_FILE} |awk -F'|' '{print $1}' > ${CACHE_FILE_TMP}  && . ${CACHE_FILE_TMP} && rm -f  ${CACHE_FILE_TMP} ;
OSTYPE=`uname`;       
HOSTNAME=`hostname`;  
WHOAMI=`whoami`;  
INSTANCE=`whoami`; 
DFT_DBNAME=${1-SAMPLE};
cd ${SNAPSHOT_DIR}
GetCurrTimestamp(){
    fmt=${1-"%Y-%m-%d %H:%M:%S"} ;
    date "+${fmt}" ;
}
#########################################################################################################

#get dbm & db snapshot 

db2 +o connect to ${DFT_DBNAME};
[[ $? != "0" ]] && echo "connect to ${DFT_DBNAME} fail! " && exit;

TS=`GetCurrTimestamp "%Y%m%d-%H%M%S"` ;
SNAP_UNIQUE_ID=`GetCurrTimestamp "%Y%m%d%H%M%S"`;

DBM_SNAPSHOT_FILE=${HOSTNAME}_${INSTANCE}_${DFT_DBNAME}_${TS}.dbm.snapshot ;
DB_SNAPSHOT_FILE=${HOSTNAME}_${INSTANCE}_${DFT_DBNAME}_${TS}.db.snapshot ;
APP_SNAPSHOT_FILE=${HOSTNAME}_${INSTANCE}_${DFT_DBNAME}_${TS}.app.snapshot ;
SQL_RESULT_FILE=${HOSTNAME}_${INSTANCE}_${DFT_DBNAME}_${TS}.sql.result ;

touch ${DBM_SNAPSHOT_FILE} ${DB_SNAPSHOT_FILE} ${APP_SNAPSHOT_FILE} ${SQL_RESULT_FILE} ;

db2 get snapshot for dbm > ${DBM_SNAPSHOT_FILE} ;
db2 get snapshot for db on $DFT_DBNAME > ${DB_SNAPSHOT_FILE} ;
db2 get snapshot for applications  on $DFT_DBNAME >${APP_SNAPSHOT_FILE} ;

#db2 -v "export to MON_GET_INSTANCE.${TS}.ixf of ixf SELECT varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,current_timestamp snapshot_timestamp,t.* FROM TABLE (MON_GET_INSTANCE(-2)) t with ur " ;
#db2 -v "export to MON_GET_DATABASE.${TS}.ixf of ixf SELECT varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,current_timestamp snapshot_timestamp,t.* from TABLE (MON_GET_DATABASE(-2) ) t with ur " ;
db2 -v "export to SNAPDBM.${TS}.ixf of ixf SELECT varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,t.* FROM SYSIBMADM.SNAPDBM t with ur " ;
db2 -v "export to SNAPDB.${TS}.ixf of ixf SELECT varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,t.* FROM SYSIBMADM.SNAPDB t with ur " ;
db2 -v "export to MON_GET_DATABASE.${TS}.ixf of ixf SELECT varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,current_timestamp snapshot_timestamp,t.* from TABLE (MON_GET_DATABASE(-2) ) t with ur " ;
db2 -v "export to MON_GET_CONNECTION.${TS}.ixf of ixf SELECT varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,current_timestamp snapshot_timestamp,t.* from TABLE (MON_GET_CONNECTION(NULL, -2)) t with ur " ;
#db2 -v "export to MON_GET_AGENT.${TS}.ixf of ixf SELECT varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,current_timestamp snapshot_timestamp,t.* from TABLE(MON_GET_AGENT(CAST(NULL AS VARCHAR(128)), CAST(NULL AS VARCHAR(128)), 1, -2)) t with ur " ;
db2 -v "export to MON_GET_MEMORY_SET.${TS}.ixf of ixf select varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,current_timestamp snapshot_timestamp,t.* FROM table(MON_GET_MEMORY_SET(NULL, CURRENT_SERVER, -2)) t with ur " ;
db2 -v "export to MON_GET_TABLESPACE.${TS}.ixf of ixf select varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,current_timestamp snapshot_timestamp,t.* FROM table(MON_GET_TABLESPACE('',-2)) t with ur " ;
db2 -v "export to MON_GET_APPL_LOCKWAIT.${TS}.ixf of ixf select varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,current_timestamp snapshot_timestamp,t.* FROM table(MON_GET_APPL_LOCKWAIT(NULL,-2)) t with ur ";
db2 -v "export to MON_GET_PKG_CACHE_STMT.${TS}.ixf of ixf select varchar('${SNAP_UNIQUE_ID}',16) as SNAP_UNIQUE_ID,current_timestamp snapshot_timestamp,t.* from TABLE(MON_GET_PKG_CACHE_STMT ( 'D', NULL, NULL, -2)) as T where (decfloat(TOTAL_ACT_TIME) / decfloat(NUM_EXECUTIONS) ) > 1000 with ur ";


#check database summary
echo "################check database summary################ " >> ${SQL_RESULT_FILE} ;
db2 "with t as (
    select 
        current timestamp as  snapshot_time,DB_CONN_TIME,timestampdiff(2,current timestamp - db_conn_time) as db_response_time,
        commit_sql_stmts + int_commits as TOTAL_COMMITS,rollback_sql_stmts + int_rollbacks  as TOTAL_ROLLBACKS,
        commit_sql_stmts + int_commits + rollback_sql_stmts + int_rollbacks as TOTAL_TRANS,
        LOCK_ESCALS,LOCK_TIMEOUTS,LOCK_WAIT_TIME,LOCK_WAITS,DEADLOCKS,LOCK_LIST_IN_USE,NUM_LOG_BUFFER_FULL,
        pool_data_l_reads + pool_temp_data_l_reads +pool_index_l_reads + pool_temp_index_l_reads +pool_xda_l_reads + pool_temp_xda_l_reads as logical_reads,pool_data_p_reads + pool_temp_data_p_reads +pool_index_p_reads + pool_temp_index_p_reads +pool_xda_p_reads + pool_temp_xda_p_reads as physical_reads
    FROM SYSIBMADM.SNAPDB a 
) select DEC(decfloat(TOTAL_TRANS)/decfloat(DB_RESPONSE_TIME),10,3) as db_tps,t.*,
    CASE WHEN logical_reads > 0
     THEN DEC((1 - (FLOAT(physical_reads) / FLOAT(logical_reads))) * 100,5,2)
     ELSE NULL
    END AS HIT_RATIO
from t with ur " >> ${SQL_RESULT_FILE} ;


#check application 
echo "################check app wait pc################ " >> ${SQL_RESULT_FILE} ;
db2 " WITH PCTWAIT AS (
     SELECT SUM(TOTAL_WAIT_TIME)AS WAIT_TIME, 
            SUM(TOTAL_RQST_TIME)AS RQST_TIME,
            COUNT(*) as CONNECT_COUNT
     FROM TABLE(MON_GET_CONNECTION(NULL,NULL)) AS METRICS)
     SELECT CONNECT_COUNT,WAIT_TIME,
            RQST_TIME,
     CASE WHEN RQST_TIME > 0 
     THEN DEC((FLOAT(WAIT_TIME))/FLOAT(RQST_TIME) * 100,5,2) 
     ELSE NULL END AS WAIT_PCT FROM PCTWAIT with ur " >> ${SQL_RESULT_FILE} ;

#check memory & buffer pool & tbsp & logs
echo && echo && echo "################check memory set################ " >> ${SQL_RESULT_FILE} ;
db2 "SELECT varchar(memory_set_type, 20) as set_type,
       varchar(db_name, 20) as dbname,
       memory_set_used as memory_set_used_kb,
       memory_set_used_hwm as memory_set_used_hwm_kb
    FROM TABLE(MON_GET_MEMORY_SET(NULL, CURRENT_SERVER, -2)) with ur "  >> ${SQL_RESULT_FILE} ;
       
echo && echo && echo "################check memory pool################ " >> ${SQL_RESULT_FILE} ;
db2 "SELECT varchar(memory_set_type, 20) AS set_type,
       varchar(memory_pool_type,20) AS pool_type,
       varchar(db_name, 20) AS dbname,
       memory_pool_used as memory_pool_used_kb,
       memory_pool_used_hwm as memory_pool_used_hwm_kb
    FROM TABLE(MON_GET_MEMORY_POOL(NULL, CURRENT_SERVER, -2)) with ur " >> ${SQL_RESULT_FILE} ;

echo && echo && echo "################check bp hit_ratio pc################ ">> ${SQL_RESULT_FILE} ;
db2 "WITH BPMETRICS AS (
    SELECT bp_name,
           pool_data_l_reads + pool_temp_data_l_reads +
           pool_index_l_reads + pool_temp_index_l_reads +
           pool_xda_l_reads + pool_temp_xda_l_reads as logical_reads,
           pool_data_p_reads + pool_temp_data_p_reads +
           pool_index_p_reads + pool_temp_index_p_reads +
           pool_xda_p_reads + pool_temp_xda_p_reads as physical_reads,
           member
    FROM TABLE(MON_GET_BUFFERPOOL('',-2)) AS METRICS)
   SELECT  VARCHAR(bp_name,20) AS bp_name, logical_reads, physical_reads,
    CASE WHEN logical_reads > 0
     THEN DEC((1 - (FLOAT(physical_reads) / FLOAT(logical_reads))) * 100,5,2)
     ELSE NULL
    END AS HIT_RATIO,member
   FROM BPMETRICS with ur " >> ${SQL_RESULT_FILE} ;

echo && echo && echo "################check tbspace################ ">> ${SQL_RESULT_FILE} ;
db2 " with t as (
SELECT 
varchar(t.TBSP_NAME,20) name,varchar(t.TBSP_TYPE,4) type,decode(t.TBSP_AUTO_RESIZE_ENABLED,1,'Y',0,'N') as resize, 
varchar(t.TBSP_STATE,10) STATE, t.TBSP_PAGE_SIZE psize, t.TBSP_USED_PAGES USED, t.TBSP_FREE_PAGES FREE,
t.TBSP_USABLE_PAGES TOTAL, dec(decfloat(TBSP_USED_PAGES)/decfloat(TBSP_USABLE_PAGES),5,2)*100 as USED_PC,t.TBSP_MAX_PAGE_TOP HWM,
pool_data_l_reads + pool_temp_data_l_reads +
pool_index_l_reads + pool_temp_index_l_reads +
pool_xda_l_reads + pool_temp_xda_l_reads as lreads,
pool_data_p_reads + pool_temp_data_p_reads +
pool_index_p_reads + pool_temp_index_p_reads +
pool_xda_p_reads + pool_temp_xda_p_reads as preads
FROM TABLE(MON_GET_TABLESPACE('',-2)) AS t ) 
select t.*,
  CASE WHEN lreads > 0
   THEN DEC((1 - (FLOAT(preads) / FLOAT(lreads))) * 100,5,2)
   ELSE NULL
  END AS HIT_RATIO from t with ur " >> ${SQL_RESULT_FILE} ;
 
echo && echo && echo "################check logs################ ">> ${SQL_RESULT_FILE} ;
db2 "SELECT varchar(T.DB_NAME,15) DB_NAME, T.LOG_UTILIZATION_PERCENT PERCENT, T.TOTAL_LOG_USED_KB USED_K, T.TOTAL_LOG_AVAILABLE_KB FREE_K,T.TOTAL_LOG_USED_KB+T.TOTAL_LOG_AVAILABLE_KB  TOTAL_K, T.TOTAL_LOG_USED_TOP_KB HWM FROM SYSIBMADM.LOG_UTILIZATION T  with ur  " >> ${SQL_RESULT_FILE} ;
   
db2 reset monitor all ;
   
TAR_NAMR=${HOSTNAME}_${INSTANCE}_${DFT_DBNAME}_${TS}.tar ;

tar -cvf ${TAR_NAMR} *${TS}*.snapshot *${TS}*.ixf *${TS}*.result  && gzip ${TAR_NAMR} && rm -rf /tmp/*.snapshot /tmp/*.ixf ;

find ${SNAPSHOT_DIR} -name "${HOSTNAME}_${INSTANCE}_${DFT_DBNAME}*.tar.gz" -mtime ${SAVE_DAYS} -type f -exec rm -rf {} \;
