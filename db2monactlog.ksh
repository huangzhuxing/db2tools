#!/bin/ksh
#################################################################################
## Function: 监控活动日志hold住的情况                                           #
## Only support AIX and single instance node now.                               #
##                                                                              #
## Version: 1.0                                                                 #
## Author: huangzhuxing  mail:hzhux@cn.ibm.com                                  #
## Date: 2017-11-08                                                             #
##                                                                              #
## Usage: ./db2monactlog.ksh <DBNAME>                                           #
##                                                                              #
##                                                                              #
#################################################################################

__VERSION__="1.0" ;
#debug option:
DEBUG_MODE=true ;

#当事务日志使用率达到多少百分比进行预警(0~100)
WARNING_PER=30

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
cd ${SNAPSHOT_DIR} ;
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


LOGS_USED_PER=$(db2 -x "select LOG_UTILIZATION_PERCENT from sysibmadm.LOG_UTILIZATION where DB_NAME=upper('${DFT_DBNAME}') fetch first rows only  ") ;
HOLD_LOG_ID="" ;
if (( ${LOGS_USED_PER} >= ${WARNING_PER} )) ; then 
    HOLD_LOG_ID=$(db2 get snapshot for db on ${DFT_DBNAME} |grep -i "Appl id holding the oldest transaction" |awk -F"=" '{print $2}');
    HOLD_LOG_ID=`echo "${HOLD_LOG_ID// /}"` ;
    db2 get snapshot for application agentid ${HOLD_LOG_ID} > ${HOSTNAME}_${INSTANCE}_${DFT_DBNAME}_${TS}.app.${HOLD_LOG_ID}.snapshot  ;
    TAR_NAME=${HOSTNAME}_${INSTANCE}_${DFT_DBNAME}_${TS}.tar ;
    tar -cvf ${TAR_NAME} *${TS}*.snapshot  && gzip ${TAR_NAME} && rm -rf /tmp/*.snapshot ;
    find ${SNAPSHOT_DIR} -name "${HOSTNAME}_${INSTANCE}_${DFT_DBNAME}*.tar.gz" -mtime ${SAVE_DAYS} -type f -exec rm -rf {} \;
fi;




