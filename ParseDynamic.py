# -*- coding: utf-8 -*-
'''
Created on 2017年12月11日
@author: zhuxingtongxue <huangzhuxing@gmail.com>
name : ParseDynamic
usage: python ParseDynamic.py -h
example:
    #从快照里面获取平均运行时间超过0.1秒（-s）的前2条（-n）sql，并且sql含有DBMCFG关键字，
    #同时输出执行计划（-e只用db2expln，再加-d使用db2exfmt输出明细的执行计划）
    $ db2 get snapshot for dynamic sql  on testcmb  |python ParseDynamic.py -s 0.1 -n 2 -r DBMCFG -e -d

'''
import sys,os,re,traceback
from optparse import OptionParser


v_parser = OptionParser()

v_parser.add_option(
    "-s", "--avgsec",                           # 操作指令
    action="store",                             # 存储的指定指
    dest="avgsec",                              # 存储的变量
    default=None,                               # 默认值
    type="float",                               # 变量类型
    metavar="second",                           # 帮助信息提示
    help=u"只获取平均执行时间大于N秒的sql",     # 显示的帮助信息
)

v_parser.add_option( "-r", "--avgread", action="store", dest="avgread", default=None, type="float", metavar="avgread",
    help=u"只获取平均读取大于N行的sql", )
    
v_parser.add_option( "-w", "--avgwrite", action="store", dest="avgwrite", default=None, type="float", metavar="avgwrite",
    help=u"只获取平均写入大于N行的sql", )                                                   

v_parser.add_option( "-S", "--avgsort", action="store", dest="avgsort", default=None, type="float", metavar="avgsort",
    help=u"只获取平均排序大于N次的sql", )                                                   

v_parser.add_option( "-O", "--avgsortoverflow", action="store", dest="avgsortoverflow", default=None, type="float", metavar="avgsortoverflow",
    help=u"只获取平均排序溢出大于N次的sql", )                                                   

v_parser.add_option( "-b", "--avgbuffhitratio", action="store", dest="avgbuffhitratio", default=None, type="float", metavar="avgbuffhitratio",
    help=u"只获取平均缓冲池命中率出小于N的sql", )                                                   

v_parser.add_option( "-e", "--explan", action="store_true", dest="explan", default=False, 
    help=u"是否同时生成执行计划", )                                                   

v_parser.add_option( "-d", "--detail", action="store_true", dest="detail", default=False,
    help=u"是否生成db2exfmt的详细执行计划", )                                                   

v_parser.add_option( "-a", "--advis" , action="store_true", dest="advis", default=False,
    help=u"是否同时生成db2advis索引建议", )                                                   

v_parser.add_option( "-R", "--regex", action="store", dest="regex", default="", type="string", metavar="regex",
    help=u"匹配sql的正则表达式", )

v_parser.add_option( "-n", "--topnum", action="store", dest="topnum", default=0, type="int", metavar="topnum",
    help=u"只获取平均执行时间TOP-N条sql", )

v_parser.add_option( "--order-by-rowsread", action="store_const",  dest="orderbyrowsread", const=True,  default=False, metavar="orderbyrowsread",
    help=u"是否按有效读进行降序排序，默认按时间排序,指定-n或者--topnum参数时有效", )

v_parser.add_option( "-m", "--schema", action="store", dest="schema", default=None, type="string", metavar="schema",
    help=u"解析sql的执行计划时，指定默认的schema", )


(v_options, args) = v_parser.parse_args()

BEGIN_STR='Number of executions'                                        #dynamic sql开始
END_STR='Statement text'                                                #dynamic sql结束
DB_NAME='Database name'                                                 #数据库名称
TOTAL_EXEC_TIME='Total execution time (sec.microsec)'                   #总运行时间
NUM_OF_EXEC='Number of executions'                                      #执行次数
ROWS_READ='Rows read'                                                   #行读取
ROWS_WRITTEN='Rows written'                                             #行写入
INTE_ROWS_UPDATED='Internal rows updated'                               #内部行更新
INTE_ROWS_DELETED='Internal rows deleted'                               #内部行删除
INTE_ROWS_INSERTED='Internal rows inserted'                             #内部行插入
SORTS='Statement sorts'                                                 #排序次数
SORT_OVERFLOWS='Statement sort overflows'                               #排序溢出次数
SORT_TIME='Total sort time'                                             #排序时间
BP_DATA_L='Buffer pool data logical reads'                              #缓冲池数据逻辑读次数
BP_DATA_P='Buffer pool data physical reads'                             #缓冲池数据物理读次数
BP_DATA_TMP_L='Buffer pool temporary data logical reads'                #缓冲池数据临时逻辑读次数
BP_DATA_TMP_P='Buffer pool temporary data physical reads'               #缓冲池数据临时物理读次数
BP_IDX_L='Buffer pool index logical reads'                              #缓冲池索引逻辑读次数
BP_IDX_P='Buffer pool index physical reads'                             #缓冲池索引物理读次数
BP_IDX_TMP_L='Buffer pool temporary index logical reads'                #缓冲池索引临时逻辑读次数
BP_IDX_TMP_P='Buffer pool temporary index physical reads'               #缓冲池索引临时物理读次数
BP_XDA_L='Buffer pool xda logical reads'                                #缓冲池XDA逻辑读次数
BP_XDA_P='Buffer pool xda physical reads'                               #缓冲池XDA物理读次数
BP_XDA_TMP_L='Buffer pool temporary xda logical reads'                  #缓冲池XDA临时逻辑读次数
BP_XDA_TMP_P='Buffer pool temporary xda physical reads'                 #缓冲池XDA临时物理读次数
STMT_TEXT='Statement text'                                              #动态sql

lam_not_zore_int = lambda x : int(x) == 0 and 1 or int(x)
lam_not_zore_float = lambda x : float(x) == 0 and 1.0 or float(x)
lam_avg_exec_time = lam_avg_sort = lam_avg_write = lam_avg_update = lam_avg_read = lambda rows,execnum: float(rows) / lam_not_zore_float(execnum) 
lam_bp_xda_hit_ratio = lam_bp_idx_hit_ratio = lam_bp_data_hit_ratio = lambda l,tl,p,tp:( lam_not_zore_float(int(p) + int(tp) )  / lam_not_zore_float(int(l)+int(tl)) )*100.0
lam_bp_hit_ratio = lambda l1,l2,l3,l4,l5,l6,p1,p2,p3,p4,p5,p6:(lam_not_zore_float(int(p1)+int(p2)+int(p3)+int(p4)+int(p5)+int(p6)) /lam_not_zore_float(int(l1)+int(l2)+int(l3)+int(l4)+int(l5)+int(l6))) * 100

v_output_sum = 0 

def PrintDynFormat(dyn_dict_list):
    global v_output_sum
    for v_dyn_dict in dyn_dict_list:
        v_output_sum = v_output_sum + 1
        print "{0:<40s}\t{1:<20s} \n{2} ".format('项目','实际值','-'*50)
        print "{0:<40s}\t{1:<20.2f}".format('平均运行时间(s)',lam_avg_exec_time(v_dyn_dict[TOTAL_EXEC_TIME],v_dyn_dict[NUM_OF_EXEC]))
        print "{0:<40s}\t{1:<20.2s}".format('运行次数',v_dyn_dict[NUM_OF_EXEC])
        print "{0:<40s}\t{1:<20.2f}".format('平均读取行数',lam_avg_read(v_dyn_dict[ROWS_READ],v_dyn_dict[NUM_OF_EXEC]))
        print "{0:<40s}\t{1:<20.2f}".format('平均写行数',lam_avg_write(v_dyn_dict[ROWS_WRITTEN],v_dyn_dict[NUM_OF_EXEC]))
        print "{0:<40s}\t{1:<20.2f}".format('平均排序次数',lam_avg_sort(v_dyn_dict[SORTS],v_dyn_dict[NUM_OF_EXEC]))
        print "{0:<40s}\t{1:<20.2f}".format('平均排序溢出次数',lam_avg_sort(v_dyn_dict[SORT_OVERFLOWS],v_dyn_dict[NUM_OF_EXEC]))
        print "{0:<40s}\t{1:<20.2f}".format('平均排序时间(ms)',lam_avg_sort(v_dyn_dict[SORT_TIME],v_dyn_dict[NUM_OF_EXEC]))
        print "{0:<40s}\t\t{1:<20.2f}".format('缓冲池命中率(百分比)',lam_bp_hit_ratio(v_dyn_dict[BP_DATA_L],v_dyn_dict[BP_DATA_TMP_L],v_dyn_dict[BP_IDX_L],v_dyn_dict[BP_IDX_TMP_L],v_dyn_dict[BP_XDA_L],v_dyn_dict[BP_XDA_TMP_L],v_dyn_dict[BP_DATA_P],v_dyn_dict[BP_DATA_TMP_P],v_dyn_dict[BP_IDX_P],v_dyn_dict[BP_IDX_TMP_P],v_dyn_dict[BP_XDA_P],v_dyn_dict[BP_XDA_TMP_P]))
        print "{0:<40s}\t\t{1:<20.2f}".format('数据缓冲池命中率(百分比)',lam_bp_data_hit_ratio(v_dyn_dict[BP_DATA_L],v_dyn_dict[BP_DATA_TMP_L],v_dyn_dict[BP_DATA_P],v_dyn_dict[BP_DATA_TMP_P]))
        print "{0:<40s}\t\t{1:<20.2f}".format('索引缓冲池命中率(百分比)',lam_bp_idx_hit_ratio(v_dyn_dict[BP_IDX_L],v_dyn_dict[BP_IDX_TMP_L],v_dyn_dict[BP_IDX_P],v_dyn_dict[BP_IDX_TMP_P]))
        print "{0:<40s}\t{1:<20.2f}".format('XDA池命中率(百分比)',lam_bp_xda_hit_ratio(v_dyn_dict[BP_XDA_L],v_dyn_dict[BP_XDA_TMP_L],v_dyn_dict[BP_XDA_P],v_dyn_dict[BP_XDA_TMP_P]))
        print "{0:<40s}{1:<20s}".format('SQL',v_dyn_dict[STMT_TEXT])
        v_flag,v_schema,v_pkgname=False,None,None
        if v_options.explan:
            print "{0:<40s}\t{1:<20s}".format('生成执行计划:','')
            
            try:
                if v_dyn_dict[STMT_TEXT].upper().startswith('CALL'):
                    v_arr = re.split('\.|\(',re.split('\s+',v_dyn_dict[STMT_TEXT])[1])
                    v_procname=v_arr[-2] if len(v_arr)==3 else v_arr[-1]
                    v_sql = '''db2 connect to %s 2>/dev/null && db2 -x "select varchar(b.BSCHEMA,10) concat '|' concat varchar(b.BNAME,20) as pkgname from syscat.procedures a join sysibm.sysdependencies b on a.SPECIFICNAME=b.DNAME where a.PROCNAME = upper('%s' ) and b.BTYPE ='K' for read only with ur"'''%(gv_dbname,v_procname)
                    v_result=os.popen(v_sql).readlines()[-1].replace('\n','').strip()
                    v_schema,v_pkgname = v_result.split('|') if v_result.strip() != '' else (None,None)
                    
                v_flag_str = '******************** EXPLAIN INSTANCE ********************' if v_options.detail  else 'Estimated Cost'
                if v_options.detail  and v_schema is None: #todo 后续再增加db2exfmt解析存储过程，暂时使用db2expln
                    v_os_cmd = u''' db2 connect to %s 2>/dev/null %s && db2 explain plan with snapshot for "%s" && db2exfmt -d "%s"  -1 -t '''% \
                                    (gv_dbname,(' && db2 set current schema  %s 2>/dev/null '%v_options.schema if v_options.schema else ''),v_dyn_dict[STMT_TEXT],gv_dbname , )
                else:
                    if v_schema :
                        v_os_cmd = u''' db2expln -d %s -c %s -p %s -g -i -t '''%(gv_dbname,v_schema,v_pkgname,) 
                    else:
                        with open('.dyn_tmp', 'w+') as v_sqlfile: 
                            if v_options.schema: 
                                v_sqlfile.write("set schema %s\n" %v_options.schema)
                            v_sqlfile.write(v_dyn_dict[STMT_TEXT])
                        v_os_cmd = u''' db2expln -d %s -f .dyn_tmp -g -i -t '''%(gv_dbname,) 
                #print v_os_cmd,
                for v_line in os.popen(v_os_cmd).readlines() :
                    v_flag = v_line.startswith(v_flag_str) if not v_flag else v_flag
                    if v_flag:
                        print v_line,
                    
            except:
                traceback.print_exc()
                print "{0:<40s}\t{1:<20s}".format('生成执行失败!','')
        if v_options.advis and v_schema is None:
            v_os_cmd,v_flag = u''' db2advis -d %s -stmt "%s" -t 1 %s ''' %(gv_dbname,v_dyn_dict[STMT_TEXT],' -q %s '%v_options.schema if v_options.schema else '' ),False
            
            print "{0:<40s}\t{1:<20s}".format('生成索引建议:','')
            try:
                for v_line in os.popen(v_os_cmd).readlines() :
                    v_flag = v_line.startswith('') if not v_flag else v_flag
                    if v_flag:
                        print v_line,
            except:            
                pass
        print '-'*50+'\n\n'
    pass
    
def ParseDynmaicSql():
    v_dyn_begin_flag,v_head_flag=False,True
    v_head_str,v_value_str,v_dyn_dict,v_dyn_dict_list = [],[],{},[]
    
    v_out_file = open('dynamic_sql.csv', 'w+')
    if not sys.stdin.isatty():
        
        for v_line in sys.stdin.readlines():
            v_arr = v_line.strip().split("=",1)
            if len(v_arr) == 1:
                continue
            v_key,v_value = v_arr
            if not v_dyn_begin_flag:
                v_dyn_begin_flag = v_key.find(BEGIN_STR) >= 0
                global gv_dbname
                gv_dbname = v_value.strip().replace('\n','') if v_key.find(DB_NAME) >= 0 else gv_dbname
            
            if v_dyn_begin_flag :
                if v_head_flag:
                    v_head_str.append(v_key.strip()) 
                v_value_str.append(v_value.strip().replace('\n','')) 
                v_dyn_dict[v_key.strip()] = v_value.strip().replace('\n','')
                if v_arr[0].find(END_STR) >= 0:
                    v_dyn_begin_flag=False
                    if v_head_flag :
                        v_out_file.write(u'"%s"\n'%('","'.join(v_head_str)))
                        v_head_flag = False
                    
                    if v_options.regex != '' and len(re.findall(v_options.regex,v_dyn_dict[STMT_TEXT])) == 0:
                        continue
                    
                    if float(v_dyn_dict[TOTAL_EXEC_TIME]) > 0 and int(v_dyn_dict[NUM_OF_EXEC]) > 0 and \
                                ( (v_options.avgsec is None or (v_options.avgsec is not None and lam_avg_exec_time(v_dyn_dict[TOTAL_EXEC_TIME],v_dyn_dict[NUM_OF_EXEC]) > v_options.avgsec ) ) and \
                                  (v_options.avgread is None or (v_options.avgread is not None and lam_avg_read(v_dyn_dict[ROWS_READ],v_dyn_dict[NUM_OF_EXEC]) > v_options.avgread ) ) and \
                                  (v_options.avgwrite is None or (v_options.avgwrite is not None and lam_avg_write(v_dyn_dict[ROWS_WRITTEN],v_dyn_dict[NUM_OF_EXEC]) > v_options.avgwrite ) ) and \
                                  (v_options.avgsort is None or (v_options.avgsort is not None and lam_avg_sort(v_dyn_dict[SORTS],v_dyn_dict[NUM_OF_EXEC]) > v_options.avgsort ) ) and \
                                  (v_options.avgsortoverflow is None or (v_options.avgsortoverflow is not None and lam_avg_sort(v_dyn_dict[SORT_OVERFLOWS],v_dyn_dict[NUM_OF_EXEC]) > v_options.avgsortoverflow ) ) and \
                                  (v_options.avgbuffhitratio is None or (v_options.avgbuffhitratio is not None and lam_bp_hit_ratio(v_dyn_dict[BP_DATA_L],v_dyn_dict[BP_DATA_TMP_L],v_dyn_dict[BP_IDX_L],v_dyn_dict[BP_IDX_TMP_L],v_dyn_dict[BP_XDA_L],v_dyn_dict[BP_XDA_TMP_L],v_dyn_dict[BP_DATA_P],v_dyn_dict[BP_DATA_TMP_P],v_dyn_dict[BP_IDX_P],v_dyn_dict[BP_IDX_TMP_P],v_dyn_dict[BP_XDA_P],v_dyn_dict[BP_XDA_TMP_P]) < v_options.avgbuffhitratio ) )  \
                                ):
                        #如果参数为None，则忽略，否则则需要符合
                        if v_options.topnum > 0 :
                            v_dyn_dict_list.append(v_dyn_dict)
                        else:
                            PrintDynFormat([v_dyn_dict])
                        v_out_file.write('"%s"\n'%('","'.join(v_value_str)) )
                    
                    v_value_str,v_dyn_dict =[],{}
                    
        v_out_file.close()
        if v_options.topnum > 0 and len(v_dyn_dict_list) > 0:
            v_dyn_dict_list_new,i = [],1
            if v_options.orderbyrowsread:
                v_dyn_dict_list.sort(key=lambda x:lam_avg_read(x[ROWS_READ],x[NUM_OF_EXEC]),reverse = True)
            else:
                v_dyn_dict_list.sort(key=lambda x:lam_avg_exec_time(x[TOTAL_EXEC_TIME],x[NUM_OF_EXEC]),reverse = True)
            for v_dyn_dict in v_dyn_dict_list:
                v_dyn_dict_list_new.append(v_dyn_dict)
                i = i+1
                if i > v_options.topnum:
                    break
            del v_dyn_dict_list
            PrintDynFormat(v_dyn_dict_list_new)
        print '符合条件的SQL为：%d条'%(v_output_sum),    
    pass
if __name__ == '__main__':
    ParseDynmaicSql()
    pass
