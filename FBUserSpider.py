# encoding=utf-8
import time
import xmlrpc.client
import logging,sys
import datetime
import random

import common
from common import *
import FBUserHelper,FBUserCrawler
from utility import OurFBAccount
from utility import FBHelper,FBBaseUser
from loghelper.loghelper import logHelper

import socket

#远程服务代理
serverconfig = common.getDispatchServerConfig()  # 3
serProxy = xmlrpc.client.ServerProxy('http://{0}:{1}'.format(serverconfig[0], serverconfig[1]))

# def getatask(taskType):
#    return serProxy.getATask(taskType)

def getFBUserTask(tasktype):
   return serProxy.getATaskUser(tasktype)
def reportFBTaskUserComplete(taskid,runningState,completeDescription):
   return serProxy.reportFBTaskUserComplete(taskid,runningState,completeDescription)


def main():
    fbuserhelper = FBUserHelper.FBUserHelper()
    # 登录
    # fbAccount = ourFBAccount('trumpJACK2018@outlook.com', '1qaz@WSX3edc', None)
    fbAccount = OurFBAccount.getAccount('ourFBAccount.txt')
    logName = time.strftime('%Y-%m-%d', time.localtime(time.time())) + "--"
    myargs = {'fName': logName, 'fLevel': logging.DEBUG}
    logger = logHelper.getLogger('myLog', logging.INFO, **myargs)
    # 初始化
    logger.info("============================================================")
    browser, isLogin = FBUserCrawler.initCrawler("https://www.facebook.com/", fbAccount)
    if not isLogin:
        logHelper.getLogger().info("login error.please check the log file!")
        time.sleep(10)
        exit(1)

    hn = socket.gethostname()
    ip = socket.gethostbyname(hn)
    spidername = '[{}]/{}'.format(ip,hn)
    
    
    while True:
        try:
            # 注意休眠
            while True:
                h = datetime.datetime.now().hour
                # print(datetime.datetime.now())
                if h < 7 or h >= 22:
                    time.sleep(random.randint(300, 1200))  # 随机睡眠 5分钟到20分钟
                else:
                    if h == 7:
                        # 早8点到早10点之间随机选择开始爬取
                        time.sleep(random.randint(3601, 7201))  # 随机一小时到俩小时分钟后开始爬取
                        logHelper.getLogger().info(
                            'Crawle begin at : ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        if browser == None:
                            browser, isLogin = FBUserCrawler.initCrawler("https://www.facebook.com/", fbAccount)
                            if not isLogin:
                                logHelper.getLogger().info("login error.please check the log file!")
                                time.sleep(10)
                                exit(1)
                        break
                    elif h >= 20:
                        # 晚8点到晚9点随机结束
                        rndTime = random.randint(0, 7201)
                        tmpTime = datetime.datetime.now() + datetime.timedelta(seconds=rndTime)
                        if tmpTime.hour >= 22:
                            logHelper.getLogger().info(
                                'Crawle end at : ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            time.sleep(rndTime)  # 睡到22点后
                            if browser != None:
                                FBUserCrawler.LogOut(browser)
                                browser.close()
                                browser = None

                        else:
                            break
                    else:
                        break


            if common.testDispatchServer() == 'Disconnected!':  #1.测试调度服务器连接
                logHelper.getLogger().info('Dispatch server is disconnected!')
                time.sleep(5)
                continue
            logHelper.getLogger().info('Dispatch server is connected!')

            logHelper.getLogger().debug('connecting database server ...')
            if common.testDatabaseServer() == 'Disconnected!':  #2.测试服务器连接
                logHelper.getLogger().info('Database server is disconnected!,trying again later.')
                time.sleep(5)
                continue
            print('Database server is connected!')

            spiderType = 'Facebook.userInfo'    #对应任务类型
            task = getFBUserTask(spiderType)

            taskid = task['id']
            if int(taskid) == -1:
                time.sleep(5)
                continue

            fbid = task['fbid']
            originalfbid = task['originalfbid']
            deep = int(task['deep'])     #当前任务深度，在保存tb_user_friends时+1保存入库
            name = task['name']
            priority = task['priority']

            fbUser = FBBaseUser(fbid,name,deep,priority)

            # logHelper.getLogger().debug(task)
            logHelper.getLogger().info('Spider [{0}] have got a task:{1}/{2}/{3}. spider is working...'.format(spiderType,taskid,fbid,originalfbid))
            time.sleep(1)
            #开始单线程爬取工作#####################################################################################################
            try:
                # 填写分配任务时间和承担的spider=''
                fbuserhelper.UpdateTaskDispatch(int(taskid),spider = spidername[:50])

                resCrawled = FBUserCrawler.crawleInfo(browser, fbUser, fbAccount)
                if resCrawled == 1:
                    #完成工作,入库
                    print('Spider have done the job. Saving the results...')

                    #告知调度端完成情况
                    print('Spider have saved the results,and reporting the job to dispatch server...')
                    k = reportFBTaskUserComplete(taskid, 2, 'completed normally.')
                    print('task id:{0},fbid:{1} has reported the job status.'.format(taskid,fbid))
                elif resCrawled == 0:
                    logHelper.getLogger().warning('network error or unknown error! wait and try...')
                    k = reportFBTaskUserComplete(taskid, 3, 'completed abnormally.Reason:network error or unknown error!')
                    time.sleep(50)
                elif resCrawled == 2:
                    print('our facebook account is forbiddened. Stop and change the account.')
                    k = reportFBTaskUserComplete(taskid, 3,'completed abnormally.Reason:our facebook account {} is forbiddened'.format(fbAccount.u))
                    break
                elif resCrawled == 3:
                    print('the target facebook account is invalid. task completed.')
                    k = reportFBTaskUserComplete(taskid, 2,'completed normal.Reason:the target facebook account {} is invalid'.format(fbUser.fbid))
                    print('task id:{0},fbid:{1} has reported the job status.'.format(taskid, fbid))

            except Exception as e1:
                logHelper.getLogger().error('Scrawling error!',e1)
                reportFBTaskUserComplete(taskid, 3, 'completed abnormally.Error:{0}'.format(e1))
                #raise  e1

            time.sleep(5)
            # 结束单线程爬取工作#####################################################################################################
        except Exception as e:
            logHelper.getLogger().error(e)
            logHelper.getLogger().error('the main loop error,restart it!')
            time.sleep(50)

if __name__ == '__main__':
    main()

