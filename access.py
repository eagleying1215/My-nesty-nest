"""个人工作台密码校验；只保存带随机盐的密码摘要。"""
import base64
import hashlib
import hmac
import os


def password_hash(password):
    salt=os.urandom(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000)
    return 'pbkdf2_sha256$600000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(digest).decode()


def valid_hash(encoded):
    try:
        method,iterations,salt,digest=encoded.split('$')
        return (method=='pbkdf2_sha256' and int(iterations)==600000
                and len(base64.b64decode(salt,validate=True))==16
                and len(base64.b64decode(digest,validate=True))==32)
    except (ValueError,TypeError):
        return False


def verify_password(password,encoded):
    if not valid_hash(encoded):return False
    _,iterations,salt,expected=encoded.split('$')
    actual=hashlib.pbkdf2_hmac('sha256',password.encode(),base64.b64decode(salt),int(iterations))
    return hmac.compare_digest(actual,base64.b64decode(expected))
