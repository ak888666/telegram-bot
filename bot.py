#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
print("===== Bot 精简稳定版（已移除 /hn /gx /sms /3ys，新增 /sjhsc /sfzsc /jmq 免费）=====")

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
import time, json, io, tempfile, requests, urllib3, logging, re, random, threading, hashlib, hmac, urllib.parse, base64, itertools, marshal, zlib
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackQueryHandler
from flask import Flask, request, jsonify

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

# 收费常量（保留原有）
KHZC_COST = 1.0        # 空号检测
YS_COST = 1.0          # 二要素

# ===== JSON存储 =====
USERS_FILE = "users.json"
USERS_BACKUP = "users.json.bak"

def load_users():
    global users
    users = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
            if isinstance(users, dict):
                print(f"✅ 成功加载 {len(users)} 个用户")
                save_users()
                return
        except Exception as e:
            print(f"⚠️ 读取 users.json 失败: {e}")
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
            if os.path.exists(USERS_FILE):
                os.rename(USERS_FILE, USERS_FILE + ".corrupt")
                print("⚠️ 已备份损坏文件为 users.json.corrupt")
            users = {}
            save_users()
    else:
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

# ===== 身份证生成（原 /sfz 功能） =====
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
KHZC_PHONE = 500
SFZ_NAME,SFZ_ID,SFZ_NATION,SFZ_ADDR,SFZ_EXPIRY,SFZ_PHOTO=range(6)
PLC_NAME,PLC_ID,PLC_ADDR_CONFIRM,PLC_ADDR_MANUAL,PLC_PHOTO=range(10,15)

# ---------- 新增免费命令状态 ----------
SJHSC_TEMPLATE, SJHSC_LOCATION = range(700, 702)
SFZSC_TEMPLATE, SFZSC_GENDER = range(703, 705)
JMQ_FILE = 800   # 混淆器状态

# ===== 代理池功能 =====
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
           f"/sjhsc → 手机号段生成器（免费）\n"
           f"/sfzsc → 身份证号列表生成（免费）\n"
           f"/jmq → Python脚本混淆加密（免费）\n"   # 这里改为 /jmq，并放在 sfzsc 后面
           f"/khzc → 空号检测（{KHZC_COST}积分）\n"
           f"/2ys → 二要素核实（{YS_COST}积分）\n"
           f"/qf → QQ反查历史\n"
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

# 新增：当在对话中收到其他命令时，提示并结束对话
def cancel_with_prompt(update, context):
    if update.message.text == '/cancel':
        return cancel(update, context)
    context.user_data.clear()
    update.message.reply_text("已取消✅重新点一下命令")
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

# ===== sfz 生成身份证（图片+PDF） =====
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

# ===== /2ys 二要素 =====
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

# ============================================================================
# 新增免费功能 1：/sjhsc 手机号段生成器
# ============================================================================
PROVINCE_CITY_DB = {
    "北京市": ["北京市"], "天津市": ["天津市"], "上海市": ["上海市"], "重庆市": ["重庆市"],
    "河北省": ["石家庄市", "唐山市", "秦皇岛市", "邯郸市", "邢台市", "保定市", "张家口市", "承德市", "沧州市", "廊坊市", "衡水市"],
    "山西省": ["太原市", "大同市", "阳泉市", "长治市", "晋城市", "朔州市", "晋中市", "运城市", "忻州市", "临汾市", "吕梁市"],
    "内蒙古自治区": ["呼和浩特市", "包头市", "乌海市", "赤峰市", "通辽市", "鄂尔多斯市", "呼伦贝尔市", "巴彦淖尔市", "乌兰察布市"],
    "辽宁省": ["沈阳市", "大连市", "鞍山市", "抚顺市", "本溪市", "丹东市", "锦州市", "营口市", "阜新市", "辽阳市", "盘锦市", "铁岭市", "朝阳市", "葫芦岛市"],
    "吉林省": ["长春市", "吉林市", "四平市", "辽源市", "通化市", "白山市", "松原市", "白城市"],
    "黑龙江省": ["哈尔滨市", "齐齐哈尔市", "鸡西市", "鹤岗市", "双鸭山市", "大庆市", "伊春市", "佳木斯市", "七台河市", "牡丹江市", "黑河市", "绥化市"],
    "江苏省": ["南京市", "无锡市", "徐州市", "常州市", "苏州市", "南通市", "连云港市", "淮安市", "盐城市", "扬州市", "镇江市", "泰州市", "宿迁市"],
    "浙江省": ["杭州市", "宁波市", "温州市", "嘉兴市", "湖州市", "绍兴市", "金华市", "衢州市", "舟山市", "台州市", "丽水市"],
    "安徽省": ["合肥市", "芜湖市", "蚌埠市", "淮南市", "马鞍山市", "淮北市", "铜陵市", "安庆市", "黄山市", "滁州市", "阜阳市", "宿州市", "六安市", "亳州市", "池州市", "宣城市"],
    "福建省": ["福州市", "厦门市", "莆田市", "三明市", "泉州市", "漳州市", "南平市", "龙岩市", "宁德市"],
    "江西省": ["南昌市", "景德镇市", "萍乡市", "九江市", "新余市", "鹰潭市", "赣州市", "吉安市", "宜春市", "抚州市", "上饶市"],
    "山东省": ["济南市", "青岛市", "淄博市", "枣庄市", "东营市", "烟台市", "潍坊市", "济宁市", "泰安市", "威海市", "日照市", "临沂市", "德州市", "聊城市", "滨州市", "菏泽市"],
    "河南省": ["郑州市", "开封市", "洛阳市", "平顶山市", "安阳市", "鹤壁市", "新乡市", "焦作市", "濮阳市", "许昌市", "漯河市", "三门峡市", "南阳市", "商丘市", "信阳市", "周口市", "驻马店市"],
    "湖北省": ["武汉市", "黄石市", "十堰市", "宜昌市", "襄阳市", "鄂州市", "荆门市", "孝感市", "荆州市", "黄冈市", "咸宁市", "随州市"],
    "湖南省": ["长沙市", "株洲市", "湘潭市", "衡阳市", "邵阳市", "岳阳市", "常德市", "张家界市", "益阳市", "郴州市", "永州市", "怀化市", "娄底市"],
    "广东省": ["广州市", "深圳市", "珠海市", "汕头市", "佛山市", "韶关市", "湛江市", "肇庆市", "江门市", "茂名市", "惠州市", "梅州市", "汕尾市", "河源市", "阳江市", "清远市", "东莞市", "中山市", "潮州市", "揭阳市", "云浮市"],
    "广西壮族自治区": ["南宁市", "柳州市", "桂林市", "梧州市", "北海市", "防城港市", "钦州市", "贵港市", "玉林市", "百色市", "贺州市", "河池市", "来宾市", "崇左市"],
    "海南省": ["海口市", "三亚市", "三沙市", "儋州市"],
    "四川省": ["成都市", "自贡市", "攀枝花市", "泸州市", "德阳市", "绵阳市", "广元市", "遂宁市", "内江市", "乐山市", "南充市", "眉山市", "宜宾市", "广安市", "达州市", "雅安市", "巴中市", "资阳市"],
    "贵州省": ["贵阳市", "六盘水市", "遵义市", "安顺市", "毕节市", "铜仁市"],
    "云南省": ["昆明市", "曲靖市", "玉溪市", "保山市", "昭通市", "丽江市", "普洱市", "临沧市"],
    "西藏自治区": ["拉萨市", "日喀则市", "昌都市", "林芝市", "山南市", "那曲市"],
    "陕西省": ["西安市", "铜川市", "宝鸡市", "咸阳市", "渭南市", "延安市", "汉中市", "榆林市", "安康市", "商洛市"],
    "甘肃省": ["兰州市", "嘉峪关市", "金昌市", "白银市", "天水市", "武威市", "张掖市", "平凉市", "酒泉市", "庆阳市", "定西市", "陇南市"],
    "青海省": ["西宁市", "海东市"],
    "宁夏回族自治区": ["银川市", "石嘴山市", "吴忠市", "固原市", "中卫市"],
    "新疆维吾尔自治区": ["乌鲁木齐市", "克拉玛依市", "吐鲁番市", "哈密市"],
    "台湾省": ["台北市", "新北市", "桃园市", "台中市", "台南市", "高雄市"],
    "香港特别行政区": ["香港特别行政区"],
    "澳门特别行政区": ["澳门特别行政区"],
}
PHONE_PREFIXES = {
    "移动": ["134","135","136","137","138","139","147","150","151","152","157","158","159","172","178","182","183","184","187","188","195","197","198"],
    "联通": ["130","131","132","145","155","156","166","175","176","185","186","196"],
    "电信": ["133","149","153","173","177","180","181","189","190","191","193","199"],
    "虚拟": ["162","165","167","170","171"],
}

class PhoneGenerator:
    def __init__(self):
        self.all_cities = self._build_city_index()
    def _build_city_index(self):
        index = {}
        for province, cities in PROVINCE_CITY_DB.items():
            for city in cities:
                index[city] = province
        return index
    def validate_pattern(self, pattern):
        cleaned = re.sub(r'[^0-9xX]', '', pattern)
        if len(cleaned) != 11:
            return False, f"手机号必须是11位 (当前{len(cleaned)}位)", []
        x_positions = [i for i, char in enumerate(cleaned) if char.lower() == 'x']
        if not x_positions:
            return False, "模板中必须包含至少一个x作为模糊位", []
        if len(x_positions) > 8:
            return False, "模糊位过多,建议不超过8位", []
        return True, cleaned, x_positions
    def find_location(self, query):
        query = query.strip()
        if query in PROVINCE_CITY_DB:
            if query in ["北京市","天津市","上海市","重庆市"]:
                return (query, query)
            return (query, "")
        for province, cities in PROVINCE_CITY_DB.items():
            for city in cities:
                if query in city or city in query:
                    return (province, city)
        for province, cities in PROVINCE_CITY_DB.items():
            if query in province:
                return (province, "")
            for city in cities:
                if query in city.replace("市","").replace("省",""):
                    return (province, city)
        return None
    def generate_numbers(self, pattern, x_positions):
        numbers = []
        num_x = len(x_positions)
        for i in range(10 ** num_x):
            num_str = str(i).zfill(num_x)
            phone_list = list(pattern)
            for idx, pos in enumerate(x_positions):
                phone_list[pos] = num_str[idx]
            numbers.append(''.join(phone_list))
        return numbers
    def filter_by_prefix(self, numbers):
        result = {"移动": [], "联通": [], "电信": [], "虚拟": [], "未知": []}
        for num in numbers:
            prefix = num[:3]
            found = False
            for operator, prefixes in PHONE_PREFIXES.items():
                if prefix in prefixes:
                    result[operator].append(num)
                    found = True
                    break
            if not found:
                result["未知"].append(num)
        return result

def sjhsc_start(update, context):
    context.user_data.clear()
    update.message.reply_text("📱 请输入手机号模板（如 130xxxxxx08，x为模糊位）：")
    return SJHSC_TEMPLATE

def sjhsc_template(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("已取消✅重新点一下命令")
        return ConversationHandler.END
    pattern = update.message.text.strip()
    gen = PhoneGenerator()
    is_valid, msg, x_positions = gen.validate_pattern(pattern)
    if not is_valid:
        update.message.reply_text(f"❌ {msg}\n请重新输入：")
        return SJHSC_TEMPLATE
    context.user_data['sjhsc_pattern'] = msg
    context.user_data['sjhsc_xpos'] = x_positions
    update.message.reply_text(f"✅ 模板有效，将生成 {10**len(x_positions)} 个号码\n📍 请输入目标地区（如：安徽省阜阳市）：")
    return SJHSC_LOCATION

def sjhsc_location(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("已取消✅重新点一下命令")
        return ConversationHandler.END
    location = update.message.text.strip()
    gen = PhoneGenerator()
    result = gen.find_location(location)
    if not result:
        update.message.reply_text("❌ 未找到该地区，请重新输入：")
        return SJHSC_LOCATION
    province, city = result
    full_location = f"{province}{city}" if city else province
    context.user_data['sjhsc_location'] = full_location
    update.message.reply_text(f"⏳ 正在生成，请稍候...")
    try:
        numbers = gen.generate_numbers(context.user_data['sjhsc_pattern'], context.user_data['sjhsc_xpos'])
        if not numbers:
            update.message.reply_text("❌ 生成失败，请检查模板。")
            return ConversationHandler.END
        categorized = gen.filter_by_prefix(numbers)
        stats_lines = [f"📍 地区：{full_location}", f"📊 共生成 {len(numbers)} 个号码"]
        for op, nums in categorized.items():
            if nums:
                stats_lines.append(f"  {op}：{len(nums)} 个")
        stats_text = "\n".join(stats_lines)
        content = "\n".join(numbers)
        bio = io.BytesIO(content.encode('utf-8'))
        bio.name = "sjhsc_list.txt"
        update.message.reply_document(document=bio, filename="sjhsc_list.txt", caption=f"✅ 生成完成\n{stats_text}")
    except Exception as e:
        update.message.reply_text(f"❌ 生成出错：{e}")
    finally:
        context.user_data.clear()
    return ConversationHandler.END

# ============================================================================
# 新增免费功能 2：/sfzsc 身份证号列表生成器
# ============================================================================
DQM_API_URL = "https://xiaowunb.top/dqm.json"
diquma = {}

def init_diquma():
    global diquma
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(DQM_API_URL, headers=headers)
        with urllib.request.urlopen(req, context=ssl._create_unverified_context(), timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
        if isinstance(resp_data, dict):
            diquma = resp_data
            print(f"🟢 地区码加载成功:{len(diquma)} 条")
        else:
            print("🔴 地区码数据格式错误")
    except Exception as e:
        print(f"🔴 地区码加载失败:{e}")

def address_lookup(pattern):
    pattern = pattern.lower().replace('x', r'\d')
    regex = re.compile(f'^{pattern}$')
    return [code for code in diquma.keys() if regex.match(code)]

def calculate_check_digit(first_17):
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_chars = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
    try:
        s = sum(int(first_17[i]) * weights[i] for i in range(17))
        return check_chars[s % 11]
    except:
        return None

def generate_ids(card_template, gender=None):
    card = card_template.lower()
    if len(card) != 18:
        print("❌ 长度必须为18位")
        return []

    addr_pat = card[:6]
    year_pat = card[6:10]
    mon_pat = card[10:12]
    day_pat = card[12:14]
    seq_pat = card[14:17]
    check_pat = card[17]

    if 'x' in addr_pat:
        addr_list = address_lookup(addr_pat)
        if not addr_list:
            print("❌ 未匹配到地区码")
            return []
        print(f"🏢 匹配到 {len(addr_list)} 个地区")
    else:
        addr_list = [addr_pat]
        print(f"🏢 地区:{diquma.get(addr_pat, '未知')}")

    if 'x' in year_pat:
        yr_input = "1990-2005"
        y1, y2 = 1990, 2005
        year_range = (y1, y2)
    else:
        year_range = (int(year_pat), int(year_pat))

    mon_digits = []
    for i, ch in enumerate(mon_pat):
        if ch == 'x':
            mon_digits.append(['0', '1'] if i == 0 else list('0123456789'))
        else:
            mon_digits.append([ch])

    day_digits = []
    for i, ch in enumerate(day_pat):
        if ch == 'x':
            day_digits.append(['0', '1', '2', '3'] if i == 0 else list('0123456789'))
        else:
            day_digits.append([ch])

    if gender not in ['男', '女']:
        if seq_pat[-1] != 'x':
            last = seq_pat[-1]
            gender = '男' if last in '13579' else '女' if last in '02468' else None
        else:
            gender = None

    seq_digits = []
    for i, ch in enumerate(seq_pat):
        if ch == 'x':
            if i == 2:
                if gender == '男':
                    seq_digits.append(['1', '3', '5', '7', '9'])
                elif gender == '女':
                    seq_digits.append(['0', '2', '4', '6', '8'])
                else:
                    seq_digits.append(list('0123456789'))
            else:
                seq_digits.append(list('0123456789'))
        else:
            seq_digits.append([ch])

    total = len(addr_list) * (year_range[1]-year_range[0]+1) * \
            len(list(itertools.product(*mon_digits))) * \
            len(list(itertools.product(*day_digits))) * \
            (1 if seq_pat[-1] != 'x' and gender else 10 if not gender else 5)
    print(f"📊 总组合数约为 {total}")

    valid = set()
    processed = 0
    start = time.time()

    for addr in addr_list:
        for year in range(year_range[0], year_range[1]+1):
            y_str = str(year)
            for m_combo in itertools.product(*mon_digits):
                m_str = ''.join(m_combo)
                m_int = int(m_str)
                if m_int < 1 or m_int > 12:
                    continue
                if m_int in (4,6,9,11):
                    max_d = 30
                elif m_int == 2:
                    max_d = 29 if ((year%4==0 and year%100!=0) or (year%400==0)) else 28
                else:
                    max_d = 31
                for d_combo in itertools.product(*day_digits):
                    d_str = ''.join(d_combo)
                    d_int = int(d_str)
                    if d_int < 1 or d_int > max_d:
                        continue
                    for s_combo in itertools.product(*seq_digits):
                        s_str = ''.join(s_combo)
                        first17 = addr + y_str + m_str + d_str + s_str
                        check = calculate_check_digit(first17)
                        if check is None:
                            continue
                        if check_pat != 'x' and check.upper() != check_pat.upper():
                            continue
                        full_id = first17 + check
                        valid.add(full_id)
                        processed += 1
                        if processed % 1000 == 0:
                            print(f"⏳ 已生成 {processed} 个...")

    print(f"✅ 生成完成,耗时 {time.time()-start:.2f} 秒,共 {len(valid)} 个有效身份证")
    return list(valid)

def sfzsc_start(update, context):
    context.user_data.clear()
    update.message.reply_text("🔢 请输入18位身份证模板（x为通配符，如 1101011990xxxx123X）：")
    return SFZSC_TEMPLATE

def sfzsc_template(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("已取消✅重新点一下命令")
        return ConversationHandler.END
    template = update.message.text.strip()
    if len(template) != 18:
        update.message.reply_text("❌ 必须为18位，请重新输入：")
        return SFZSC_TEMPLATE
    if not all(c in '0123456789xX' for c in template):
        update.message.reply_text("❌ 只能包含数字和 x/X，请重新输入：")
        return SFZSC_TEMPLATE
    if len(template.replace('x','').replace('X','')) < 6:
        update.message.reply_text("❌ 至少输入6位已知数字，请重新输入：")
        return SFZSC_TEMPLATE
    context.user_data['sfzsc_template'] = template
    update.message.reply_text("👤 请输入性别（男/女，直接回车表示未知）：")
    return SFZSC_GENDER

def sfzsc_gender(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("已取消✅重新点一下命令")
        return ConversationHandler.END
    gender = update.message.text.strip()
    if gender not in ['男', '女']:
        gender = None
    template = context.user_data.get('sfzsc_template')
    if not template:
        update.message.reply_text("❌ 会话已过期，请重新 /sfzsc")
        return ConversationHandler.END
    update.message.reply_text(f"⏳ 正在生成身份证号，请稍候...")
    try:
        valid_ids = generate_ids(template, gender)
        if not valid_ids:
            update.message.reply_text("❌ 未生成任何有效身份证号，请检查模板。")
            return ConversationHandler.END
        content = "\n".join(valid_ids)
        bio = io.BytesIO(content.encode('utf-8'))
        bio.name = "sfz.txt"
        update.message.reply_document(document=bio, filename="sfz.txt", caption=f"✅ 共生成 {len(valid_ids)} 个身份证号")
    except Exception as e:
        update.message.reply_text(f"❌ 生成出错：{e}")
    finally:
        context.user_data.clear()
    return ConversationHandler.END

# ============================================================================
# 新增免费功能 3：/jmq 脚本混淆加密（原 /obfuscate 改为 /jmq）
# ============================================================================
# 混淆器辅助函数
_look = list('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_')
def _name(l=8):
    first = random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_')
    return first + ''.join(random.choices(_look, k=l-1))

def random_alphanum(l=4):
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(random.choices(chars, k=l))

def junk(cnt):
    parts = []
    for _ in range(cnt):
        name = _name()
        val = random.choice([
            str(random.randint(0, 999)),
            repr(random_alphanum(3)),
            str(random.random())[:6],
            'True' if random.getrandbits(1) else 'False'
        ])
        parts.append(f'{name}={val}')
    return ';'.join(parts)

def random_split(text, min_len=30, max_len=50):
    pieces, idx = [], 0
    while idx < len(text):
        seg_len = random.randint(min_len, max_len)
        pieces.append(text[idx:idx+seg_len])
        idx += seg_len
    return pieces

def obfuscate_code(code):
    # 1. 压缩和序列化
    compiled = marshal.dumps(compile(code, '<string>', 'exec'))
    compressed = zlib.compress(compiled)
    # 2. XOR 加密(单字节异或)
    key = random.randint(1, 255)
    xor_data = bytes([b ^ key for b in compressed])
    b85_data = base64.b85encode(xor_data).decode()
    # 3. 构建解密执行脚本(仅 4 行核心代码)
    body_core = f'''import sys, os, base64, marshal, zlib
k={key}
exec(marshal.loads(zlib.decompress(bytes([b^k for b in base64.b85decode("{b85_data}")]))))'''
    # 4. 混淆处理
    outer_b64 = base64.b64encode(body_core.encode()).decode()
    fragments = random_split(outer_b64)
    frag_names = [_name() for _ in fragments]
    list_name = _name()
    junk_cnt = random.randint(20, 40)
    junk_pool = junk(junk_cnt).split(';')
    for idx, (name, piece) in enumerate(zip(frag_names, fragments)):
        junk_pool.insert(random.randint(0, len(junk_pool)), f'{name}={repr(piece)}')
    head = ';'.join(junk_pool)
    tail = junk(random.randint(5, 10))
    rejoin = f'{list_name}=[{",".join(frag_names)}];exec(__import__("base64").b64decode("".join({list_name})))'
    return '# 天天开心\n' + head + ';' + rejoin + ';' + tail

def jmq_start(update, context):
    context.user_data.clear()
    update.message.reply_text("📄 请发送一个 .py 脚本文件，我将进行混淆加密并返回已加密版本。")
    return JMQ_FILE

def jmq_file(update, context):
    if update.message.text and update.message.text.startswith('/'):
        context.user_data.clear()
        update.message.reply_text("已取消✅重新点一下命令")
        return ConversationHandler.END
    if not update.message.document:
        update.message.reply_text("❌ 请发送一个 .py 文件（以附件形式）。")
        return JMQ_FILE
    doc = update.message.document
    if not doc.file_name.endswith('.py'):
        update.message.reply_text("❌ 只接受 .py 文件，请重新发送。")
        return JMQ_FILE
    # 下载文件
    file = doc.get_file()
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as tmp:
        file.download(tmp.name)
        tmp_path = tmp.name
    try:
        with open(tmp_path, 'r', encoding='utf-8', errors='surrogateescape') as f:
            code = f.read()
        # 混淆
        obfuscated = obfuscate_code(code)
        # 生成输出文件名
        base_name = os.path.splitext(doc.file_name)[0]
        out_name = f"已加密{base_name}.py"
        out_io = io.BytesIO(obfuscated.encode('utf-8'))
        out_io.name = out_name
        update.message.reply_document(document=out_io, filename=out_name, caption=f"✅ 混淆完成，已加密为 {out_name}")
    except Exception as e:
        update.message.reply_text(f"❌ 混淆失败：{e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        context.user_data.clear()
    return ConversationHandler.END

# ===== 主程序 =====
def main():
    global bot
    # 初始化地区码（用于 sfzsc）
    init_diquma()
    updater=Updater(BOT_TOKEN, request_kwargs={'read_timeout':60,'connect_timeout':30})
    bot=updater.bot
    dp=updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
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
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(Filters.command, cancel_with_prompt)],
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
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(Filters.command, cancel_with_prompt)],
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
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(Filters.command, cancel_with_prompt)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('qf', qf_start)],
        states={QF_QQ: [MessageHandler(Filters.text, qf_qq)]},
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(Filters.command, cancel_with_prompt)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('2ys', ys_start)],
        states={
            YS_NAME: [MessageHandler(Filters.text, ys_name)],
            YS_ID: [MessageHandler(Filters.text, ys_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(Filters.command, cancel_with_prompt)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('khzc', khzc_start)],
        states={KHZC_PHONE: [MessageHandler(Filters.text & ~Filters.command, khzc_phone)]},
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(Filters.command, cancel_with_prompt)],
        allow_reentry=True
    ))

    # ---------- 新增免费命令 ----------
    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('sjhsc', sjhsc_start)],
        states={
            SJHSC_TEMPLATE: [MessageHandler(Filters.text & ~Filters.command, sjhsc_template)],
            SJHSC_LOCATION: [MessageHandler(Filters.text & ~Filters.command, sjhsc_location)],
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(Filters.command, cancel_with_prompt)],
        allow_reentry=True
    ))

    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('sfzsc', sfzsc_start)],
        states={
            SFZSC_TEMPLATE: [MessageHandler(Filters.text & ~Filters.command, sfzsc_template)],
            SFZSC_GENDER: [MessageHandler(Filters.text & ~Filters.command, sfzsc_gender)],
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(Filters.command, cancel_with_prompt)],
        allow_reentry=True
    ))

    # ---------- /jmq 混淆器（放在 sfzsc 后面） ----------
    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('jmq', jmq_start)],
        states={
            JMQ_FILE: [MessageHandler(Filters.document, jmq_file)],
        },
        fallbacks=[CommandHandler('cancel', cancel), MessageHandler(Filters.command, cancel_with_prompt)],
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
