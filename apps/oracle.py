#!/usr/bin/env python
# *-* coding:utf8 *-*
# sky

import subprocess
from lib import database, mail, log, warning
import datetime
#from lib import conf
#from lib.tools import format_size
#from lib.printf import printf
import shutil

'''
def info():
    check, awr_hours=conf.get("oracle", 
            "check", 
            "awr_hours"
            )
    
    if check=="1":
        printf("Oracle信息:")
        # 表空间
        printf("表空间信息:")
        sql="""
        set heading off trimspool on feedback off pagesize 0 linesize 1000
        SELECT a.tablespace_name ,
          a.bytes,
          ( a.bytes - b.bytes ),
          b.bytes,
          Round(( ( a.bytes - b.bytes ) / a.bytes ) * 100, 2)
        FROM  (SELECT tablespace_name,
                      SUM(bytes) bytes
                FROM  dba_data_files
                GROUP  BY tablespace_name) a,
              (SELECT tablespace_name,
                      SUM(bytes) bytes,
                      Max(bytes) largest
                FROM  dba_free_space
                GROUP  BY tablespace_name) b
        WHERE  a.tablespace_name = b.tablespace_name
        ORDER  BY ( ( a.bytes - b.bytes ) / a.bytes ) DESC;
        """
        cmd=f"su - oracle -c 'sqlplus -S / as sysdba <<EOF\n{sql}\nEOF'"
        (status, message)=subprocess.getstatusoutput(cmd)
        if status==0:
            flag=0
            printf(f"表空间名称    表空间大小    已使用表空间    未使用表空间    使用率(%)")
            for i in message.splitlines():
                i=i.split()
                row=f"{i[0]:<14}{format_size(i[1]):<14}{format_size(i[2]):<17}{format_size(i[3]):<17}{i[4]:<4}"
                printf(row)
                if float(i[4]) > 95:
                    printf(f"Oracle: {i[0]}表空间不足, 已使用{i[4]}%", 1)
                    flag=1
            if flag==0:
                printf(f"Oracle: 表空间正常", 1)

            # awr
            printf("-"*40)
            printf("awr信息:")
            awr_format="html"
            awr_file='/tmp/awr.html'
            days=4
            sql="""
            set heading off trimspool on feedback off pagesize 0
            select trim(max(snap_id)) from dba_hist_snapshot;
            """
            cmd=f"su - oracle -c 'sqlplus -S / as sysdba <<EOF\n{sql}\nEOF'"
            (status, message)=subprocess.getstatusoutput(cmd)
            max_snap_id=int(message)
            if int(awr_hours) > max_snap_id:
                awr_hours=max_snap_id
            min_snap_id=max_snap_id-int(awr_hours)
            cmd=f"""su - oracle -c"
            echo -e '{awr_format}\n{days}\n{min_snap_id}\n{max_snap_id}\n{awr_file}\n' | (sqlplus -S / as sysdba @?/rdbms/admin/awrrpt.sql)"
            """
            (status, message)=subprocess.getstatusoutput(cmd)
            if status==0:
                shutil.move(awr_file, "./report/")
                printf("请查看awr.html文件")
            else:
                printf("awr生成失败, 请手动生成")
        else:
            printf("无法连接Oracle.")
'''
def generate_awr(awr_hours):
    """生成awr
    """
    awr_format="html"
    awr_file='/tmp/awr.html'
    #awr_file="./report/"
    days=4
    sql="""
    set heading off trimspool on feedback off pagesize 0
    select trim(max(snap_id)) from dba_hist_snapshot;
    """
    cmd=f"su - oracle -c 'sqlplus -S / as sysdba <<EOF\n{sql}\nEOF'"
    (status, message)=subprocess.getstatusoutput(cmd)
    max_snap_id=int(message)
    if awr_hours > max_snap_id:
        awr_hours=max_snap_id
    min_snap_id=max_snap_id-awr_hours
    cmd=f"""su - oracle -c"
    echo -e '{awr_format}\n{days}\n{min_snap_id}\n{max_snap_id}\n{awr_file}\n' | (sqlplus -S / as sysdba @?/rdbms/admin/awrrpt.sql)"
    """
    (status, message)=subprocess.getstatusoutput(cmd)
    shutil.move(awr_file, "./report/awr.html")
    return status

def record(log_file, log_level):
    logger=log.Logger(log_file, log_level)
    logger.logger.debug("记录表空间信息")
    db=database.db()
    record_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 表空间
    sql="""
    set heading off trimspool on feedback off pagesize 0 linesize 1000
    SELECT a.tablespace_name ,
      a.bytes,
      ( a.bytes - b.bytes ),
      b.bytes,
      Round(( ( a.bytes - b.bytes ) / a.bytes ) * 100, 2)
    FROM  (SELECT tablespace_name,
                  SUM(bytes) bytes
            FROM  dba_data_files
            GROUP  BY tablespace_name) a,
          (SELECT tablespace_name,
                  SUM(bytes) bytes,
                  Max(bytes) largest
            FROM  dba_free_space
            GROUP  BY tablespace_name) b
    WHERE  a.tablespace_name = b.tablespace_name
    ORDER  BY ( ( a.bytes - b.bytes ) / a.bytes ) DESC;
    """
    cmd=f"su - oracle -c 'sqlplus -S / as sysdba <<EOF\n{sql}\nEOF'"
    (status, message)=subprocess.getstatusoutput(cmd)
    if status==0:
        data_list=[]
        for i in message.splitlines():
            i=i.split()
            data_list.append((record_time, i[0], i[1], i[2], i[4], i[3]))
        sql="insert into oracle values(?, ?, ?, ?, ?, ?)"
        db.update_all(sql, data_list)
    else:
        sql="insert into error value(?, ?, ?, ?, ?)"
        db.update_one(sql, (record_time, 'Oracle', 'connect', '无法连接Oracle', 0))
def tablespace_analysis(log_file, log_level, warning_percent, warning_interval, sender_alias, receive, subject):
    logger=log.Logger(log_file, log_level)
    db=database.db()
    sql=f"select tablespace_name, used_percent from oracle where record_time=(select max(record_time) from oracle)"
    data=db.query_all(sql)

    logger.logger.debug("分析表空间...")
    for i in data:
        flag=0                 # 是否有预警信息
        if i[1] >= warning_percent:
            flag=1
            logger.logger.warning(f"{i[0]}表空间已使用{i[1]}%")
        warning_flag=warning.warning(logger, db, flag, "oracle", i[0], warning_interval)
        if warning_flag:
            warning_msg=f"Oracle表空间预警:\n{i[0]}表空间已使用{i[1]}%"
            mail.send(logger, warning_msg, sender_alias, receive, subject, msg=i[0])

if __name__ == "__main__":
    main()
