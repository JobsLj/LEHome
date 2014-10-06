#!/usr/bin/env python
# encoding: utf-8

# Copyright 2014 Xinyu, He <legendmohe@foxmail.com>
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import urllib
import urllib2
import json
import pickle
import glob
import httplib
import os
import io
import threading
import errno
from datetime import datetime
from bs4 import BeautifulSoup
from lib.command.Command import UserInput
from util.Res import Res
from util import Util
from lib.sound import Sound
from util.log import *
from lib.model import Callback


class target_callback(Callback.Callback):
    def callback(self,
            action=None,
            target=None,
            msg=None, 
            pre_value=None):
        INFO("* target callback: %s, message: %s pre_value: %s" %(target, msg, pre_value))
        return True, "pass"


class weather_report_callback(Callback.Callback):
    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value == 'show' or pre_value == 'get':
            if pre_value == 'show':
                self._home.publish_msg(cmd, u'正在获取天气讯息...')
            try:
                city_code_url = "http://hao.weidunewtab.com/tianqi/city.php?"
                if Util.empty_str(msg):
                    city_code = '101280101'  # Guangzhou
                else:
                    city_code_url += urllib.urlencode({'city': msg.encode('utf8')})
                    city_code = urllib2.urlopen(city_code_url, timeout=10).read()
                    if city_code == 'ERROR':
                        self._home.publish_msg(cmd, u'城市代码无效')
                        ERROR("weather-city code error.")
                        return True, False
                url = 'http://hao.weidunewtab.com/myapp/weather/data/index.php?cityID=' + city_code
                re = urllib2.urlopen(url, timeout=10).read()
                re = re.decode('utf-8-sig')  # WTF!
                we = json.loads(re)['weatherinfo']
            except Exception, ex:
                ERROR(ex)
                ERROR("weather target faild.")
                return True

            content = ""
            content += u'城市：' + we['city'] + "\n"
            if msg == u"明天":
                content += u'明天天气：' + we['temp2'] + ', ' + we['weather2'] + '\n'
            elif msg == u"今天":
                content += u'今天天气：' + we['temp1'] + ', ' + we['weather1'] + '\n'
            else:
                content += u'今天天气：' + we['temp1'] + ', ' + we['weather1'] + '\n'
                content += u'明天天气：' + we['temp2'] + ', ' + we['weather2'] + '\n'
                content += u'后天天气：' + we['temp3'] + ', ' + we['weather3'] + '\n'
            content += u'穿衣指数：' + we['index_d']

            if pre_value == 'show':
                self._home.publish_msg(cmd, content)
                # self._speaker.speak(content.split('\n'))

        return True, we


class douban_callback(Callback.Callback):

    __music_table = {
        "华语":"1",
        "欧美":"2",
        "70":"3",
        "80":"4",
        "90":"5",
        "粤语":"6",
        "摇滚":"7",
        "民谣":"8",
        "轻音乐":"9",
        "电影原声":"10",
        "爵士":"13",
        "电子":"14",
        "说唱":"15",
        "R&B":"16",
        "日语":"17",
        "韩语":"18",
        "女声":"20",
        "特仑苏":"21",
        "法语":"22",
        "豆瓣音乐人":"26",
                }
    
    def callback(self,
            action=None,
            target = None,
            msg = None, 
            pre_value = None):
        if pre_value == "play":
            music_id = "9" # 轻音乐
            if msg in self.__music_table:
                music_id = self.__music_table[msg]
            play = self._global_context["player"] 
            httpConnection = httplib.HTTPConnection('douban.fm')
            httpConnection.request('GET', '/j/mine/playlist?type=n&channel=' + music_id)
            song = json.loads(httpConnection.getresponse().read())['song']
            play(song[0]['url'], inqueue=False)
        return True, "pass"


class qqfm_callback(Callback.Callback):

    base_url = 'http://' + Res.get('qqfm/server')
    channel_url = base_url + '/list'
    next_url = base_url + '/next'
    pause_url = base_url + '/pause'

    def init_channcels(self):
        self._fm_state = 0
        try:
            INFO("init qqfm:" + qqfm_callback.channel_url)
            channels = urllib2.urlopen(qqfm_callback.channel_url, timeout=5).read()
            self.channels = [channel.decode("utf-8") for channel in channels.split('\n')]
        except Exception, ex:
            ERROR("qqfm init error.")
            ERROR(ex)
            self._home.publish_msg("init qqfm", u"连接失败")
            self.channels = []

    def callback(self, cmd, action, target, msg, pre_value):
        try:
            if not hasattr(self, "channels") or len(self.channels) == 0:
                self.init_channcels()
            if len(self.channels) == 0:
                self._home.publish_msg(cmd, u"电台列表初始化失败")
                return True
            if pre_value == "show":
                if len(self.channels) == 0:
                    self._home.publish_msg(cmd, u"无电台列表")
                else:
                    info = u"电台列表:\n"
                    info += u", ".join(self.channels)
                    self._home.publish_msg(cmd, info)
            elif pre_value == "run" or pre_value == "on":
                if len(self.channels) == 0:
                    self._home.publish_msg(cmd, u"无电台列表")
                else:
                    if msg in self.channels:
                        play_url = qqfm_callback.next_url \
                                + "?" + urllib.urlencode(
                                            {'type':msg.encode('utf-8')}
                                        )
                    else:
                        play_url = qqfm_callback.next_url
                    INFO("qqfm playing:%s" % (play_url,))
                    rep = urllib2.urlopen(play_url, timeout=5).read()
                    INFO("qqfm playing state: " + rep)
                    self._home.publish_msg(cmd, u"正在播放:" + rep.decode("utf-8"))
                    self._fm_state = 1
            elif pre_value == "break" or pre_value == "off":
                rep = urllib2.urlopen(qqfm_callback.pause_url, timeout=3).read().decode("utf-8")
                INFO("qqfm playing state: " + rep)
                if rep == "pause":
                    self._fm_state = 0
                if self._fm_state == 1:
                    self._home.publish_msg(cmd, u"停止播放")
        except Exception, ex:
            ERROR("qqfm error.")
            ERROR(ex)
            self._home.publish_msg(cmd, u"播放失败")
        return True


class newsfm_callback(Callback.Callback):

    base_url = 'http://ctt.rgd.com.cn:8000'
    channel_url = base_url + '/fm914'

    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value == "play":
            play = self._global_context["player"]
            play(newsfm_callback.channel_url)
            self._home.publish_msg(cmd, u"正在播放" + target)
        return True


class message_callback(Callback.Callback):
    def callback(
            self,
            cmd,
            action=None,
            target=None,
            msg=None, 
            pre_value=None):
        if pre_value == "new":
            path = "usr/message/"
            try:
                os.makedirs(path)
            except OSError as exc:
                if exc.errno == errno.EEXIST and os.path.isdir(path):
                    pass
                else:
                    ERROR(exc)
                    return False

            self._home.setResume(True)
            filepath = path + datetime.now().strftime("%m_%d_%H_%M") + ".mp3"
            Sound.play(Res.get_res_path("sound/com_stop"))
            record = self._global_context["recorder"]
            self._home.publish_msg(cmd, u"录音开始...")
            record(filepath)
            self._home.publish_msg(cmd, u"录音结束")
            self._home.setResume(False)
        elif pre_value == "play":
            self._home.setResume(True)

            play = self._global_context["player"]
            for idx, filepath in enumerate(glob.glob("usr/message/*.mp3")):
                # self._speaker.speak(u'第%d条留言' % (idx + 1))
                INFO(u'第%d条留言:%s' % (idx + 1, filepath))
                play(filepath)
                play(Res.get_res_path("sound/com_stop"))

            self._home.setResume(False)
        elif pre_value == "remove":
            filelist = glob.glob("usr/message/*.mp3")
            for f in filelist:
                os.remove(f)
                INFO("remove:%s" % (f, ))
            Sound.play(
                        Res.get_res_path("sound/com_trash")
                        )
        return True


class record_callback(Callback.Callback):
    def callback(self,
            cmd,
            action=None,
            target=None,
            msg=None, 
            pre_value=None):
        
        if pre_value == "new":
            path = "usr/memo/"
            try:
                os.makedirs(path)
            except OSError as exc:
                if exc.errno == errno.EEXIST and os.path.isdir(path):
                    pass
                else:
                    ERROR(exc)
                    self._home.publish_msg(cmd, u"录音错误")
                    return False

            self._home.setResume(True)
            filepath = path + datetime.now().strftime("%m_%d_%H_%M") + ".mp3"
            record = self._global_context["recorder"]
            self._home.publish_msg(cmd, u"录音开始...")
            record(filepath)
            self._home.publish_msg(cmd, u"录音结束")
            Sound.play(
                        Res.get_res_path("sound/com_stop")
                        )
            self._home.setResume(False)
        return True

class bell_callback(Callback.Callback):
    def callback(self,
            action=None,
            target=None,
            msg=None, 
            pre_value=None):
        if pre_value == "play":
            if msg is None or not msg.endswith(u"次"):
                count = 5
            else:
                count = int(Util.cn2dig(msg[:-1]))
            self._home.setResume(True)
            play = self._global_context["player"]
            play(Res.get_res_path("sound/com_bell"), loop=count)
            self._home.setResume(False)
        return True


class warning_bell_callback(Callback.Callback):
    def callback(self,
            action=None,
            target=None,
            msg=None, 
            pre_value=None):
        if pre_value == "play":
            if msg is None or not msg.endswith(u"次"):
                count = 1
            else:
                count = int(Util.cn2dig(msg[:-1]))
            self._home.setResume(True)
            play = self._global_context["player"]
            play(Res.get_res_path("sound/com_warn"), loop=count)
            self._home.setResume(False)
        return True


class alarm_callback(Callback.Callback):
    def callback(self,
            cmd,
            action=None,
            target=None,
            msg=None, 
            pre_value=None):
        if pre_value == "new" or pre_value == "set":
            if msg is None:
                self._home.publish_msg(cmd, u"时间格式错误")
                return False, None

            if msg.endswith(u'点') or \
                msg.endswith(u'分'):
                t = Util.gap_for_timestring(msg)
            else:
                self._home.publish_msg(cmd, u"时间格式错误")
                return False
            if t is None:
                self._home.publish_msg(cmd, u"时间格式错误")
                return False, None

            INFO("alarm wait for %d sec" % (t, ))
            self._home.publish_msg(cmd, action + target + msg)

            threading.current_thread().waitUtil(t)
            if threading.current_thread().stopped():
                return False
            self._home.setResume(True)
            count = 7
            Sound.play( Res.get_res_path("sound/com_bell") , True, count)
            self._home.setResume(False)
            return True


class todo_callback(Callback.Callback):

    todo_path = "data/todo.pcl"

    def __init__(self):
        super(todo_callback, self).__init__()
        self._lock = threading.Lock()
        self.load_todos()

    def load_todos(self):
        self.todos = []
        with self._lock:
            try:
                with open(todo_callback.todo_path, "rb") as f:
                    self.todos = pickle.load(f)
            except:
                INFO("empty todo list.")
        return self.todos

    def save_todos(self):
        with self._lock:
            try:
                with open(todo_callback.todo_path, "wb") as f:
                    pickle.dump(self.todos, f, True)
            except Exception, e:
                ERROR(e)
                ERROR("invaild save todo path:%s", todo_callback.todo_path)

    def todo_at_index(self, index):
        if index < 0 or index >= len(self.todos):
            ERROR("invaild todo index.")
            return NULL
        else:
            return self.todos[index]

    def add_todo(self, content):
        if content is None or len(content) == 0:
            ERROR("empty todo content.")
            return False
        self.todos.append(content)
        return True

    def remove_todo_at_index(self, index):
        if index < 0 or index >= len(self.todos):
            ERROR("invaild todo index.")
            return False
        else:
            del self.todos[index]
            self.save_todos()
            return True

    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value == "show":
            info = ""
            self.load_todos()
            for index, todo in enumerate(self.todos):
                info += u"序号: %d\n    内容:%s\n"  \
                        % (index, self.todos[index])
            if len(info) == 0:
                info = u"当前无" + target
            else:
                info = info[:-1]
            self._home.publish_msg(cmd, info)
        elif pre_value == "new":
            if Util.empty_str(msg):
                cancel_flag = u"取消"
                finish_flag = u"完成"
                self._home.publish_msg(
                    cmd
                    , u"请输入内容, 输入\"%s\"或\"%s\"结束:" % (finish_flag, cancel_flag)
                    , cmd_type="input"
                )
                msg = UserInput(self._home).waitForInput(
                                                        finish=finish_flag,
                                                        cancel=cancel_flag)
            if msg is None  \
                    or not self.add_todo(msg):
                self._home.publish_msg(cmd, u"新建失败")
            else:
                self._home.publish_msg(cmd, u"新建成功")
                self.save_todos()
        elif pre_value == "remove":
            index = Util.cn2dig(msg)
            if not index is None:
                if self.remove_todo_at_index(int(index)):
                    INFO("remove todo: " + msg)
                    self._home.publish_msg(cmd
                            , u"删除" + target + ": " + msg)
                else:
                    self._home.publish_msg(cmd, u"无此编号:" + index)
            else:
                self._home.publish_msg(cmd, u"编号出错")
        return True


class task_callback(Callback.Callback):
    def callback(self, cmd, action, msg, pre_value):
        if pre_value == "show":
            threads = self._home._cmd.threads
            info = u""
            if len(threads) <= 1: #  当前任务不计入
                info += u"当前无任务"
                INFO(info)
                self._home.publish_msg(cmd, info)
            else:
                if msg is None or len(msg) == 0:
                    info += u"任务列表:"
                    for thread_index in threads:
                        if threads[thread_index][0] == cmd:
                            continue
                        info += u"\n  序号：%d 内容：%s" % (thread_index, threads[thread_index][0])
                    INFO(info)
                    self._home.publish_msg(cmd, info)
                else:
                    thread_index = Util.cn2dig(msg)
                    if thread_index is None or thread_index == '':
                        WARN("invaild thread index %s" % (msg, ))
                        self._home.publish_msg(cmd, u"任务序号格式错误:" + msg)
                    else:
                        thread_index = int(thread_index)
                        if thread_index in threads:
                            info += u"内容：%s" % (threads[thread_index][0], )
                            INFO(info)
                            self._home.publish_msg(cmd, info)
                        else:
                            WARN("invaild thread index %s" % (msg, ))
                            self._home.publish_msg(cmd, u"无此任务序号:" + msg)
        elif pre_value == "break":
            thread_index = Util.cn2dig(msg)
            if thread_index is None or thread_index == '':
                WARN("invaild thread index %s" % (msg, ))
                self._home.publish_msg(cmd, u"无此任务序号:" + msg)
                return False, None
            else:
                thread_index = int(thread_index)
            if thread_index in self._home._cmd.threads:
                cmd, thread = self._home._cmd.threads[thread_index]
                thread.stop()
                self._home.publish_msg(cmd, u"停止执行任务%d" % (thread_index, ))
                INFO("stop thread: %d with cmd: %s" % (thread_index, cmd))
            else:
                WARN("invaild thread index %s" % (thread_index, ))
                self._home.publish_msg(cmd, u"无此任务序号:" + thread_index)
        return True, True


class script_callback(Callback.Callback):

    script_path = "data/scripts.pcl"

    def __init__(self):
        super(script_callback, self).__init__()
        self._lock = threading.Lock()
        self.load_scripts()

    def load_scripts(self):
        with self._lock:
            self.scripts = {}
            try:
                with io.open(script_callback.script_path,
                                "r",
                                encoding="utf-8") as f:
                    # self.scripts = pickle.load(f)
                    for line in f.readlines():
                        script_token = line.split()
                        if(len(script_token) == 2):
                            self.scripts[script_token[0]] = script_token[1]
            except:
                INFO("empty script list.")
        return self.scripts

    def save_scripts(self):
        with self._lock:
            try:
                with io.open(script_callback.script_path,
                        "w", 
                        encoding="utf-8") as f:
                    for key in self.scripts:
                        f.write("%s %s\n" % (key, self.scripts[key]))
                    # pickle.dump(self.scripts, f, True)
            except Exception, e:
                ERROR(e)
                ERROR("invaild save script path:%s", script_callback.script_path)

    def script_by_name(self, name):
        if name in self.scripts:
            return self.scripts[name]
        return None

    def add_script(self, name, content):
        if name is None or len(name) == 0:
            ERROR("empty script name.")
            return False
        if content is None or len(content) == 0:
            ERROR("empty script content.")
            return False
        self.scripts[name] = content
        return True

    def remove_script_by_name(self, name):
        if name in self.scripts:
            del self.scripts[name]
            self.save_scripts()
            return True
        return False

    def run_script(self, name):
        script = self.script_by_name(name)
        if script is None or len(script) == 0:
            ERROR("empty script content or invaild script name.")
            return False
        else:
            self._home.parse_cmd(script)
            return True

    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value == "show":
            info = ""
            self.load_scripts()
            if msg is None or len(msg) == 0:
                for script_name in self.scripts:
                    info += u"名称: " + script_name  \
                            + u"\n    内容: " + self.scripts[script_name]  \
                            + "\n"
                if len(info) == 0:
                    info = u"当前无" + target
                else:
                    info = info[:-1]
            else:
                if msg in self.scripts:
                    info = u'内容：' + self.scripts[msg]
                else:
                    info = u"无此脚本：" + msg
            self._home.publish_msg(cmd, info)
            INFO(info)
        else:
            if msg is None or len(msg) == 0:
                self._home.publish_msg(cmd, u"缺少脚本名称")
                return False
            script_name = msg
            if pre_value == "new":
                cancel_flag = u"取消"
                finish_flag = u"完成"
                self._home.publish_msg(cmd
                        , u"脚本名称: " + script_name  \
                        + u"\n请输入脚本内容, 输入\"" + cancel_flag  \
                        + u"\"或\"" + finish_flag + u"\"结束..."
                        , cmd_type="input")
                userinput = UserInput(self._home).waitForInput(
                                                            finish=finish_flag,
                                                            cancel=cancel_flag)
                if userinput is None  \
                        or not self.add_script(script_name, userinput):
                    self._home.publish_msg(cmd, u"新建脚本失败")
                else:
                    self._home.publish_msg(cmd, u"成功新建脚本")
                    self.save_scripts()
            elif pre_value == "remove":
                if self.remove_script_by_name(script_name):
                    INFO("remove script: " + script_name)
                    self._home.publish_msg(cmd, u"删除脚本:" + script_name)
            elif pre_value == "run":
                if self.run_script(script_name) is False:
                    self._home.publish_msg(cmd, u"无效脚本")
                else:
                    self._home.publish_msg(cmd,
                                            u"执行脚本:" + script_name,
                                            cmd_type="toast")
        return True


class var_callback(Callback.Callback):

    var_path = "data/vars.pcl"

    def __init__(self):
        super(var_callback, self).__init__()
        self._lock = threading.Lock()
        self.load_vars()

    def load_vars(self):
        with self._lock:
            self.vars = {}
            try:
                with open(var_callback.var_path, "rb") as f:
                    self.vars = pickle.load(f)
            except:
                INFO("empty var list.")
        return self.vars

    def save_vars(self):
        with self._lock:
            try:
                with open(var_callback.var_path, "wb") as f:
                    pickle.dump(self.vars, f, True)
            except Exception, e:
                ERROR(e)
                ERROR("invaild save var path:%s", var_callback.var_path)

    def var_by_name(self, name):
        if name in self.vars:
            return self.vars[name]
        return None

    def add_var(self, name, content):
        if Util.empty_str(name):
            ERROR("empty var name.")
            return False
        if content is None:
            ERROR("empty var content.")
            return False
        self.vars[name] = content
        return True

    def remove_var_by_name(self, name):
        if name in self.vars:
            del self.vars[name]
            self.save_vars()
            return True
        return False

    def callback(self, cmd, action, msg, pre_value):
        if pre_value == "show":
            info = ""
            self.load_vars()
            if Util.empty_str(msg):
                for var_name in self.vars:
                    info += u"名称: " + var_name  \
                            + u"\n    内容: " + unicode(self.vars[var_name])  \
                            + "\n"
                if len(info) == 0:
                    info = u"当前无变量列表"
                else:
                    info = info[:-1]
            else:
                if msg not in self.vars:
                    info = u"无变量:" + msg
                else:
                    info = u"内容为:" + unicode(self.vars[msg])
            self._home.publish_msg(cmd, info)
            INFO(info)
        elif pre_value == "get":
            self.load_vars()
            if Util.empty_str(msg):
                self._home.publish_msg(cmd, u"缺少变量名称")
                return False
            # import pdb; pdb.set_trace()
            if msg not in self.vars:
                self._home.publish_msg(cmd, u"无变量:" + msg)
                return False
            else:
                # INFO(u'变量:' + unicode(self.vars[msg]))
                return True, self.vars[msg]
        else:
            if Util.empty_str(msg):
                self._home.publish_msg(cmd, u"缺少变量名称")
                return False
            if pre_value == "new" or pre_value == "set":
                spos = msg.find(u'为')
                if spos != -1:
                    var_name = msg[:spos]
                    var_value = msg[spos + 1:]
                    parse_value = Util.var_parse_value(var_value)
                    if parse_value is None:
                        ERROR("var_parse_value error.")
                        return False
                elif pre_value != None:
                    var_name = msg
                    parse_value = pre_value
                else:
                    info = u"格式错误"
                    ERROR(info)
                    self._home.publish_msg(cmd, info)
                    return False
                if not self.add_var(var_name, parse_value):
                    self._home.publish_msg(cmd, u"新建变量失败")
                else:
                    if pre_value == "new":
                        self._home.publish_msg(cmd,
                                u"成功新建变量:" + var_name)
                    self.save_vars()
            elif pre_value == "remove":
                var_name = msg
                if self.remove_var_by_name(var_name):
                    INFO("remove var: " + var_name)
                    self._home.publish_msg(cmd, u"删除变量:" + var_name)
                else:
                    self._home.publish_msg(cmd, u"删除变量失败:" + var_name)
        return True


class switch_callback(Callback.Callback):
    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value == "show":
            switchs = self._home._switch.switchs
            if len(switchs) == 0:
                self._home.publish_msg(cmd, target + u"列表为空")
            else:
                info = target + u"列表:"
                for switch_ip in switchs:
                    infos = self._home._switch.show_info(switch_ip)
                    readable_info = self._home._switch.readable_info(infos)
                    switch_name = self._home._switch.name_for_ip(switch_ip)
                    info += u"\n  名称:" \
                            + switch_name \
                            + u" 状态:" \
                            + self._home._switch.show_state(switch_ip) \
                            + u"\n  " \
                            + readable_info
                self._home.publish_msg(cmd, info)
        return True


class sensor_callback(Callback.Callback):
    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value == "show":
            states = self._home._sensor.list_state()
            if states is None:
                self._home.publish_msg(cmd, u"内部错误")
            elif len(states) == 0:
                self._home.publish_msg(cmd, target + u"列表为空")
            else:
                info = target + u"列表:"
                for sensor_addr in states:
                    sensor_name = self._home._sensor.name_for_addr(sensor_addr)
                    info += u"\n  名称:" \
                            + sensor_name \
                            + u"\n  状态:" \
                            + self._home._sensor.readable_state(states[sensor_addr])
                self._home.publish_msg(cmd, info)
        return True


class normal_switch_callback(Callback.Callback):
    def callback(self, cmd, action, target, msg, pre_value):
        ip = self._home._switch.ip_for_name(target)
        if pre_value == "on":
            return True
        elif pre_value == "off":
            return True
        elif pre_value == "show" or pre_value == "get" and msg == u"状态":
            state = self._home._switch.show_state(ip)
            if state is None:
                self._home.publish_msg(cmd, u"内部错误")
                return False
            infos = self._home._switch.show_info(ip)
            readable_info = self._home._switch.readable_info(infos)
            info = u"名称:" \
                   + target \
                   + u" 状态:" \
                   + state  \
                   + u"\n  " \
                   + readable_info
            if pre_value == "show":
                self._home.publish_msg(cmd, info)
            return True, state
        else:
            return False


class normal_ril_callback(Callback.Callback):

    ON = "\x40"
    OFF = "\x41"

    def __init__(self):
        super(normal_ril_callback, self).__init__()
        self._ac = {"status":"off"}

    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value != None and len(pre_value) != 0:
            res = None
            if pre_value == "on":
                if self._ac["status"] == "off":
                    res = self._home._ril.send_cmd(normal_ril_callback.ON)
                    if res == None:
                        self._home.publish_msg(cmd, u"空调打开失败")
                    else:
                        self._home.publish_msg(cmd, u"空调打开成功")
                        self._ac["status"] = "on"
                else:
                    self._home.publish_msg(cmd, u"空调已经打开")
            elif pre_value == "off":
                if self._ac["status"] == "on":
                    res = self._home._ril.send_cmd(normal_ril_callback.OFF)
                    if res == None:
                        self._home.publish_msg(cmd, u"空调关闭失败")
                    else:
                        self._home.publish_msg(cmd, u"空调关闭成功")
                        self._ac["status"] = "off"
                else:
                    self._home.publish_msg(cmd, u"空调已经关闭")
            elif pre_value == "show":
                if self._ac["status"] == "on":
                    self._home.publish_msg(cmd, u"空调已打开")
                else:
                    self._home.publish_msg(cmd, u"空调已关闭")
            elif pre_value == "get":
                if self._ac["status"] == "on":
                    return True, "on"
                else:
                    return True, "off"
        return True, True


class normal_sensor_callback(Callback.Callback):
    def callback(self, cmd, action, target, msg, pre_value):
        addr = self._home._sensor.addr_for_name(target)
        if pre_value == "show" or pre_value == "get":
            if msg == u'温度':
                state = self._home._sensor.get_temp(addr)
                info = u'当前%s的温度为:%s℃' % (target, state)
            elif msg == u'湿度':
                state = self._home._sensor.get_humidity(addr)
                info = u'当前%s的湿度为:%s%%' % (target, state)
            elif msg == u'有人':
                state = self._home._sensor.get_pir(addr)
                if state == 1:
                    return True, True
                elif state == 0:
                    return True, False
                else:
                    INFO(u'无法获取状态：' + msg)
                    return True, False
            elif msg == u'无人' or msg == u'没人':
                state = self._home._sensor.get_pir(addr)
                if state == 0:
                    return True, True
                elif state == 1:
                    return True, False
                else:
                    INFO(u'无法获取状态：' + msg)
                    return True, True
            elif msg == u'是否有人':
                state = self._home._sensor.get_pir(addr)
                info = u'当前%s%s人' % (target, u'有' if state == 1 else u'无')
            elif msg == u'亮度' or msg == u'光照':
                state = self._home._sensor.get_lig(addr)
                info = u'当前%s的亮度为%s' % (target, state)
            else:
                state = self._home._sensor.get_sensor_state(addr)
                info = self._home._sensor.readable_state(state)
                if state is None:
                    INFO(u'无法获取状态：' + msg)
                    self._home.publish_msg(cmd, u"内部错误")
                    return False
                else:
                    self._home.publish_msg(cmd, info)
                    return True, state
            if state is None:
                INFO(u'无法获取状态：' + msg)
                self._home.publish_msg(cmd, u"内部错误")
                return False
            if pre_value == "show":
                self._home.publish_msg(cmd, info)
            return True, state
        else:
            return False


class normal_tag_callback(Callback.Callback):
    def callback(self, cmd, action, target, msg, pre_value):
        addr = self._home._tag.addr_for_name(target)
        if addr is None:
            self._home.publish_msg(cmd, u"无此目标：" + target)
            return False
        if msg.startswith(u'在'):
            here = True
            msg = msg[1:]
        elif msg.startswith(u'不在'):
            here = False
            msg = msg[2:]
        else:
            self._home.publish_msg(cmd, u"格式错误：" + cmd)
            return False
        place = self._home._tag.place_ip_for_name(msg)
        if place is None or len(place) == 0:
            self._home.publish_msg(cmd, u"无此处所：" + msg)
            return False

        if pre_value == "show" or pre_value == "get":
            res = self._home._tag.near(addr, place)
            if res is None:
                INFO(u'无法获取位置：' + cmd)
                self._home.publish_msg(cmd, u"内部错误")
                return False
            else:
                status = u"在" if res else u"不在"
                info = target + status + msg
                if here is False:
                    res = not res
            if pre_value == "show":
                self._home.publish_msg(cmd, info)
            return True, res
        else:
            return False


class speech_callback(Callback.Callback):
    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value == "play":
            if Util.empty_str(msg):
                cancel_flag = u"取消"
                finish_flag = u"完成"
                self._home.publish_msg(cmd
                        , u"请输入内容, 输入\"" + cancel_flag  \
                        + u"\"或\"" + finish_flag + u"\"结束..."
                        , cmd_type="input")
                userinput = UserInput(self._home).waitForInput(
                                                            finish=finish_flag,
                                                            cancel=cancel_flag)
                if userinput is None:
                    WARN("speech content is None.")
                    self._home.publish_msg(cmd, u"语音内容为空")
                    return True
                else:
                    self._speaker.speak(userinput)
                    self._home.publish_msg(cmd, u"播放语音:" + userinput)
            else:
                self._speaker.speak(msg)
                self._home.publish_msg(cmd, u"播放语音:" + msg)
        return True


class bus_callback(Callback.Callback):
    REQUEST_URL = "http://gzbusnow.sinaapp.com/index.php?"
    REQUEST_TIMEOUT = 10

    def _request_info(self, msg):
        url = bus_callback.REQUEST_URL + \
                urllib.urlencode({
                    'keyword': msg.encode('utf8'),
                    'a': 'query',
                    'c': 'busrunningv2'
                    })
        try:
            rep = urllib2.urlopen(
                    url,
                    timeout=bus_callback.REQUEST_TIMEOUT) \
                .read()
            return rep
        except:
            return None

    def _parse_info(self, rep):
        res = []
        soup = BeautifulSoup(rep)
        for status in soup.find_all(class_='bus_direction'):
            current = {
                    'status': unicode(status.string).strip(),
                    'nodes': []}
            # WTF?!
            begin_node = status.next_sibling.next_sibling.table.tbody
            for child in begin_node.children:
                if type(child) != type(begin_node):
                    continue
                node = {}
                if child.get('class') is None:
                    node['in'] = False
                else:
                    node['in'] = True
                # WTF?!
                node['name'] = unicode(child.contents[3].contents[0].string.strip())
                current['nodes'].append(node)
            res.append(current)
        return res

    def _bus_info(self, bus_number):
        info = self._request_info(bus_number)
        if info is None:
            return None
        else:
            parse_res = self._parse_info(info)
            if parse_res is None or len(parse_res) == 0:
                return None
            return parse_res

    def _readable_info(self, info):
        res = ""
        for direction in info:
            res += direction['status'] + u'\n'
            for node in direction['nodes']:
                line = u'|' if node['in'] is False else u'*'
                line += u" %s" % node['name']
                res += line + u'\n'
            res += u'\n'
        return res[:-2]

    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value == "show" or pre_value == "get":
            if msg is None or len(msg) == 0:
                self._home.publish_msg(cmd, u"请输入公交线路名称")
                return True, None
            self._home.publish_msg(cmd, u"正在查询...")
            info = self._bus_info(msg)
            if info is None:
                self._home.publish_msg(cmd, u"请输入正确的公交线路名称")
                return True, None
            else:
                readable_info = self._readable_info(info)
                self._home.publish_msg(cmd, readable_info)
        return True, info


class bus_station_callback(Callback.Callback):
    REQUEST_URL = "http://gzbusnow.sinaapp.com/index.php?"
    REQUEST_TIMEOUT = 10

    def _request_info(self, msg):
        url = bus_callback.REQUEST_URL + \
                urllib.urlencode({
                    'keyword': msg.encode('utf8'),
                    'a': 'query',
                    'c': 'station'
                    })
        try:
            rep = urllib2.urlopen(
                    url,
                    timeout=bus_callback.REQUEST_TIMEOUT) \
                .read()
            return rep
        except:
            return None

    def _parse_info(self, rep):
        res = []
        soup = BeautifulSoup(rep, from_encoding='utf-8')
        in_head = True
        for bus in soup.find_all('tr'):
            tds = bus.contents
            cur = {}
            if in_head:
                # cur['name'] = unicode(tds[0].string.strip())
                # cur['distance'] = unicode(tds[2].string.strip())
                # cur['info'] = unicode(tds[4].string.strip())
                in_head = False
                continue # escape header
            elif tds[3].string is not None:
                cur['name'] = unicode(tds[1].a.string.strip())
                cur['distance'] = unicode(tds[3].string.strip())
                cur['info'] = unicode(tds[5].string.strip())
            else:
                continue
            res.append(cur)
        return res

    def _bus_info(self, bus_number):
        info = self._request_info(bus_number)
        if info is None:
            return None
        else:
            parse_res = self._parse_info(info)
            if parse_res is None or len(parse_res) == 0:
                return None
            return parse_res

    def _readable_info(self, info):
        res = u""
        for bus in info:
            res += u"%s:\n  离本站%s站, 方向:%s\n\n" % (
                    bus['name'],
                    bus['distance'],
                    bus['info'])
        return res[:-2]

    def callback(self, cmd, action, target, msg, pre_value):
        if pre_value == "show" or pre_value == "get":
            if msg is None or len(msg) == 0:
                self._home.publish_msg(cmd, u"请输入公交站牌名称")
                return True, None
            self._home.publish_msg(cmd, u"正在查询...")
            info = self._bus_info(msg)
            if info is None:
                self._home.publish_msg(cmd, u"请输入正确的公交站牌名称")
                return True, None
            else:
                readable_info = self._readable_info(info)
                self._home.publish_msg(cmd, readable_info)
        return True, info


