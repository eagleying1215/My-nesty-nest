"""在自己的电脑运行此文件，启动服务并打开本机浏览器。"""
from app import main

if __name__ == '__main__':
    try:
        main(open_browser=True)
    except OSError as exc:
        print(f'启动失败：{exc}')
        print('请检查是否已经启动了工作台，或端口 8000 被其他程序占用。')
        input('按回车关闭……')
