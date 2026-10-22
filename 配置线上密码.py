"""在部署电脑或服务器运行，交互输入的密码不会回显或写入源代码。"""
from getpass import getpass
from pathlib import Path
from access import password_hash

if __name__=='__main__':
    output=Path(__file__).parent / 'deploy' / 'private.env'
    if output.exists():
        raise SystemExit('deploy/private.env 已存在。为防止覆盖，请先安全备份并移走旧配置。')
    domain=input('请输入指向服务器的域名（例如 socks.example.com，不含协议）：').strip()
    import re
    if not re.fullmatch(r'(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',domain):
        raise SystemExit('域名格式不正确，请填写实际域名。')
    username=input('登录用户名（英文字母或数字，至少3位）：').strip()
    if not re.fullmatch('[A-Za-z0-9_-]{3,64}',username):raise SystemExit('用户名格式不正确')
    password=getpass('设置密码（建议使用密码管理器生成，至少16位）：')
    if len(password)<16:raise SystemExit('密码至少16位')
    if password!=getpass('再次输入密码：'):raise SystemExit('两次密码不同')
    # Single quotes preserve dollar characters in Docker Compose env files.
    text=f"SITE_ADDRESS={domain}\nWORKBENCH_USERNAME={username}\nWORKBENCH_PASSWORD_HASH='{password_hash(password)}'\n"
    with output.open('x') as f:f.write(text)
    output.chmod(0o600)
    print('已写入 deploy/private.env，仅包含配置和加盐摘要。不要提交或分享此文件。')
