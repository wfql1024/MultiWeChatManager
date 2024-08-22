
import csv
import sqlite3

import search_wechat_key

dbDecode= search_wechat_key.wechat_db_decrypt()

def test_sqlite():
    conn =sqlite3.connect("./edit_MicroMsg.db")
    cursor= conn.cursor()
    all_friend="SELECT UserName,Alias,Remark,NickName FROM 'Contact' WHERE Type==3 and UserName not like 'gh%' and UserName NOT LIKE '%@chatroom';" # 所有的好友
    del_byOther="SELECT UserName,Alias,Remark,NickName FROM Contact WHERE type == 1 AND UserName!='medianote' AND UserName!= 'floatbottle' AND UserName!='fmessage';" # 被对方删除的人
    chat_RoomId ="SELECT UserName,Remark,NickName  FROM Contact WHERE Type ==2 AND UserName!='filehelper';" # 所有加入的聊天室
    gh="SELECT UserName,Alias,NickName FROM Contact WHERE VerifyFlag==8 OR VerifyFlag==24;"# 所有关注的公众号
    unKnowSql="SELECT UserName,Alias,Remark,NickName FROM Contact WHERE Type==0 ;"# 未知的 不是黑名单  可能是已经注销的账号
    deled_know="SELECT UserName,Alias,Remark,NickName FROM Contact WHERE Type==259;" # 被对方删除同时自己知道
    special_person="SELECT UserName,Alias,Remark,NickName FROM Contact WHERE Type==2051;" #特别关注
    noSee_friend="SELECT UserName,Alias,Remark,NickName FROM Contact WHERE Type==65539;" #主动被屏蔽朋友圈的人
    deled_unknow="SELECT UserName,Alias,Remark,NickName FROM Contact WHERE type == 1 AND UserName!='medianote' AND UserName!= 'floatbottle' AND UserName!='fmessage';" # 被对方删除但是自己不知道的
    testSql="SELECT UserName,Alias,Remark,NickName FROM 'Contact' WHERE UserName not like 'gh%' and UserName NOT LIKE '%@chatroom';"
    
    try :

        cursor.execute(testSql)
        results =cursor.fetchall()
        with open("./all_friend.csv",mode="w",encoding="utf-8",newline='') as fp:
          writer =csv.writer(fp)
          writer.writerow(['UserName','Alias','Remark','NickName' ])
          for item in results:
            writer.writerow(item)
          
    except Exception as e:
        print("sql excute have some error",e)
    conn.close()

if __name__=='__main__':
    
    # list_dirFile()
    print("开始解密数据库")
    dbDecode()
    print("数据库解密完毕")
    
    print("开始执行sql 查找想要的内容")
    test_sqlite()
    print("sql 执行完毕。。。。。。 ")
    print("执行结果在 当前路径的all_friend.csv文件中")