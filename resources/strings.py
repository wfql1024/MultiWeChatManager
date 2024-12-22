import platform

SYS_VER = int(platform.release())
NEWER_VER = True if SYS_VER >= 10 else False

class Strings:
    REMOTE_SETTING_JSON_GITEE = 'https://gitee.com/wfql1024/MultiWeChatManager/raw/master/remote_setting'
    REMOTE_SETTING_JSON_GITHUB = 'https://raw.githubusercontent.com/wfql1024/MultiWeChatManager/master/remote_setting'
    DEFAULT_AVATAR_BASE64 = "/9j/4AAQSkZJRgABAQEAAAAAAAD/4QAuRXhpZgAATU0AKgAAAAgAAkAAAAMAAAABAAAAAEABAAEAAAABAAAAAAAAAAD/2wBDAAoHBwkHBgoJCAkLCwoMDxkQDw4ODx4WFxIZJCAmJSMgIyIoLTkwKCo2KyIjMkQyNjs9QEBAJjBGS0U+Sjk/QD3/2wBDAQsLCw8NDx0QEB09KSMpPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT3/wAARCAHaAdoDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD1xnbJ5pNzetD9TSUALub1o3N60lFAC7m9aNzetJRQAu5vWjc3rSUUALub1o3N60lFAC7m9aNzetJRQAu5vWjc3rSUUALub1o3N60lFAC7m9aNzetJRQAu5vWjc3rSUUALub1o3N60lFAC7m9aNzetJRQAu5vWjc3rSUUALub1o3N60lFAC7m9aNzetJRQAu5vWjc3rSUUALub1o3N60lFAC7m9aNzetJRQAu5vWjc3rSUUALub1o3N60lFAC7m9aNzetJRQAu5vWjc3rSUUALub1o3N60lFAC7m9aNzetJRQAu5vWjc3rSUUALub1o3N60lFAC7m9aNzetJRQAu5vWjc3rSUUALub1o3N60lFAC7m9am3N61BU1AET9TSUr9TSUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABU1Q1NQBE/U0lK/U0lABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAVNUNTUARP1NJSv1NJQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFTVDU1AET9TSUr9TSUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABU1Q1NQBE/U0lK/U0lABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAVNUNTUARP1NJSv1NJQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFTVDU1AET9TSUr9TSUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUVVmvFj4B5BwaALDyKnU4qCS7QfdYVnyXLyNyeO1QUAaBv27EVH/aUvt+VU6KAL41F+5FTR3qn7zCsqigDdSZG+62afWHHM0f3TV63vgcB2oAvUUgcOAR3paACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKmqGpqAIn6mkpX6mkoAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiqt5cBEKjrj1oAZdXWMquQQazXcuSSc5oclySaSgAooooAKKKKACiiigAoyR0oooAuW14UOGJI6CtNDkA1gVoWVzjIPc45NAGhRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFTVDU1AET9TSUr9TSUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFADZH2IT6DNY9xJ5smeOnar19LsG3P3hWXQAUUUUAFFFFABRRRQAUUUUAFFFFABTkOHU+hptFAG1ay+bHnjrjipqy7GXDhM9TWpQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFTVDU1AET9TSUr9TSUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFB6GikP3T9KAMq+k3uPYVVqWY5eoqACiiigAooooAKKKKACiiigAooooAKKKKAJbc7JlPoa2Yn3oDWEnDg1s2ZzADQBNRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAVNUNTUARP1NJSv1NJQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUjfcP0paQ9D9KAMF/vn60lSSDDn61HQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAVsWP8Ax6rWQOorZs/+PZaAJqKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACpqhqagCJ+ppKV+ppKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACg9D9KKKAMa5TDioKvajHh1+lUaACiiigAooooAKKKKACiiigAooooAKKKKAHxDMgHvWzbjEIFZNquZ0+tbKDAxQAtFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABU1Q1NQBE/U0lK/U0lABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQBWvIt6E+grIrfcZBHqMVlXluY3JAOMdaAKtFFFABRRRQAUUUUAFFFFABRRRQAUUVLDG0jjAOM80AW7CLIDnsfStCmRRiNMCn0AFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABU1Q1NQBE/U0lK/U0lABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAVFcRCSMjHJqWigDDljMblT2qOtW7tg6EgDJPWstwUJB7HFACUUUUAFFFFABRRRQAUUUUAKBk1qWdv5YJI68iobO2ycsAQRxWiBgCgAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACpqhqagCJ+ppKV+ppKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooACAayr2LYS3qa1ap6iMxj60AZdFFFABRRRQAUUUUAFS28fmSYqKrmnD99n2oA0o0CIB7U6iigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACpqhqagCJ+ppKV+ppKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKpai48sAdc1alkWNMmsm5mMjnk4zxQBBRRRQAUUUUAFFFFABVuwfE2D0xVSnxuYzkHFAG7RUNtMsoA5yBzmpqACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKmqGpqAIn6mkpX6mkoAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKY8qp3H50APqGa4WIHvj0qpNfE5AHUY4NU3dmPJNAEk1yZScEgE9KgoooAKKKKACiiigAooooAKKKKAJI5WjPBNaVveLJgY9uayaUEjoaAN/I9aKyYbxo8AjPPc1oxXCyAZIBPbNAEtFGQaKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACpqhqagCJ+ppKV+ppKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAoopCcdaAFpryKn3jiq016iZAJzjjiqMty8mctwaALc99jOwqaoyStIcn1zxUdFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUqOUORSUUAX4b5hgNtAAq7HMknRgaw6kjneP7pxQBuUVRhvh0djnPHFXEkVxkUAOooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACpqhqagCJ+ppKV+ppKACiiigAooooAKKKKACiiigAooooAKKKKACignFU7m8CZUDPvQBYluFiGTzzjis2a8Z/ulh+NQSSM5JyeTTKAFJJ6nNJRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFTxXLRkZZsemagooA17e6WTAwc4zzVkHNYAJHQ1etrzHBHtyaANGikDg9CKWgAooooAKKKKACiiigAooooAKKKKACiiigAqaoamoAifqaSlfqaSgAooooAKKKKACiiigAooooAKKKKACiiigCpezbAV45FZZJJyat6l/r/wAKp0AFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQBfsrgj5Tjk1o1iW/wDrk+tbdABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABU1Q1NQBE/U0lK/U0lABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFAGXqX+vH0qnVzUgfPz7VToAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigB8H+uT61u1iW4PnL9a26ACiiigAooooAKKKKACiiigAooooAKKKKACpqhqagCJ+ppKV+ppKACiiigAooooAKKKKACiiigAooooAKKKKAK1zbiQE98YrOe3cHAVj+FbVFAGH5En9xvyo8iT+435VuUUAYfkSf3G/KjyJP7jflW5RQBh+RJ/cb8qPIk/uN+VblFAGH5En9xvyo8iT+435VuUUAYfkSf3G/KjyJP7jflW5RQBh+RJ/cb8qPIk/uN+VblFAGH5En9xvyo8iT+435VuUUAYfkSf3G/KjyJP7jflW5RQBh+RJ/cb8qPIk/uN+VblFAGH5En9xvyo8iT+435VuUUAYfkSf3G/KjyJP7jflW5RQBh+RJ/cb8qPIk/uN+VblFAGH5En9xvyo8iT+435VuUUAYfkSf3G/KlFvJ/cb8q26KAKNra45Ocg5q9RRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAVNUNTUARP1NJSv1NJQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFTVDU1AET9TSUr9TSUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABU1Q1NQBE/U0lK/U0lABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAVNUNTUARP1NJSv1NJQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFTVDU1AET9TSUr9TSUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABU1Q1NQBE/U0lK/U0lABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAVNUNTUARP1NJU3p9BRQBDRU1FAENFTUUAQ0VNRQBDRU1FAENFTUUAQ0VNRQBDRU1FAENFTUUAQ0VNRQBDRU1FAENFTUUAQ0VNRQBDRU1FAENFTUUAQ0VNRQBDRU1FAENFTUUAQ0VNRQBDRU1FAENFTUUAQ0VNRQBDRU1FAENFTUUAQ0VNRQBDRU1FAENFTUUAQ0VNRQBDRU1FAENTUU1vvH60Af/2Q=="

    REFERENCE_TEXT = ("通过python解密微信3.x数据库\n"
                      "https://www.52pojie.cn/thread-1950632-1-1.html\n"
                      "\n"
                      "如何通过python窗口句柄、后台鼠标点击\n"
                      "https://blog.csdn.net/weixin_43407838/article/details/125255441\n"
                      "\n"
                      "python通过句柄值移动窗口的位置\n"
                      "https://blog.51cto.com/u_16213427/7225602\n"
                      "\n"
                      "Python - tkinter之filedialog.askdirectory() 某个情况下无法运行的解决办法\n"
                      "https://www.cnblogs.com/flyinghou/p/14606383.html\n"
                      "\n"
                      "微信逆向之自己动手去除微信多开限制，小白也能看懂\n"
                      "https://www.52pojie.cn/thread-1951224-1-1.html\n"
                      "\n"
                      "管理员权限程序以普通用户的权限运行不需要管理员权限的程序\n"
                      "https://blog.csdn.net/qq411633267/article/details/56291270\n"
                      "\n"
                      "查看程序的所有句柄的对象类型和名称，或关闭程序的任何句柄\n"
                      "https://github.com/yihleego/pywinhandle\n"
                      "\n"
                      "使用x64dbg实现微信私聊与群消息防撤回\n"
                      "https://www.52pojie.cn/thread-1777652-1-1.html\n"
                      "\n"
                      "微信4.0及之前版本的多开与防撤回的实现\n"
                      "https://github.com/huiyadanli/RevokeMsgPatcher\n"
                      "\n"
                      "微信多开与防撤回的实现各版本特征码收集\n"
                      "https://www.52pojie.cn/thread-1964251-1-1.html\n"
                      "\n"
                      "微信4.0及之前版本的数据库解密（rust版本）\n"
                      "https://github.com/0xlane/wechat-dump-rs")

    SPONSOR_TEXT = [
        {
            'date': '24-09-13',
            'currency': '￥',
            'amount': '0.10',
            'user': '*械'
        },
        {
            'date': '24-09-30',
            'currency': '￥',
            'amount': '6.66',
            'user': '绚*9'
        },
        {
            'date': '24-10-21',
            'currency': '￥',
            'amount': '1.00',
            'user': '*叶'
        },
        {
            'date': '24-10-22',
            'currency': '￥',
            'amount': '8.88',
            'user': '*.'
        },
        {
            'date': '24-10-22',
            'currency': '￥',
            'amount': '18.88',
            'user': '*.'
        },
        {
            'date': '24-11-29',
            'currency': '￥',
            'amount': '8.88',
            'user': '*子'
        },
    ]

    AUTHOR = {
        '吾爱破解主页': 'https://www.52pojie.cn/home.php?mod=space&uid=2279503&do=thread&view=me&from=space',
        '哔哩哔哩主页': 'https://space.bilibili.com/3546733357304606',
        'GitHub主页': 'https://github.com/wfql1024',
        'Gitee主页': 'https://gitee.com/wfql1024',
    }

    THANKS = {
        'lyie15': {
            'text': 'lyie15',
            '52pj': 'https://www.52pojie.cn/home.php?mod=space&uid=2030303'
        },
        'windion': {
            'text': 'windion',
            'bilibili': 'https://space.bilibili.com/256019141',
            '52pj': 'https://www.52pojie.cn/home.php?mod=follow&uid=1529783&do=view&from=space'
        },
        'JackLSQ': {
            'text': 'JackLSQ',
            '52pj': 'https://www.52pojie.cn/home.php?mod=space&uid=1784521'
        },
        'Anhkgg': {
            'text': 'Anhkgg',
            'github': 'https://github.com/anhkgg',
        },
        'de52': {
            'text': 'de52',
            '52pj': 'https://www.52pojie.cn/home.php?mod=space&uid=1703408'
        },
        'yihleego': {
            'text': 'yihleego',
            'github': 'https://github.com/yihleego',
        },
        'cherub0507': {
            'text': 'cherub0507',
            '52pj': 'https://www.52pojie.cn/home.php?mod=space&uid=681049'
        },
        'tnxts': {
            'text': 'tnxts',
            '52pj': 'https://www.52pojie.cn/home.php?mod=space&uid=1705928'
        },
        'huiyadanli': {
            'text': 'huiyadanli',
            'github': 'https://github.com/huiyadanli'
        },
        'zetaloop': {
            'text': 'zetaloop',
            'github': 'https://github.com/zetaloop'
        },
        '0xlane': {
            'text': '0xlane',
            'github': 'https://github.com/0xlane'
        }
    }

    PROJ = {
        '吾爱破解': 'https://www.52pojie.cn/thread-1949078-1-1.html',
        'Github': 'https://github.com/wfql1024/MultiWeChatManager',
        'Gitee': 'https://gitee.com/wfql1024/MultiWeChatManager',
    }

    VIDEO_TUTORIAL_LINK = "https://www.bilibili.com/video/BV174H1eBE9r"

    NOT_ENABLED_NEW_FUNC = "by 吾峰起浪（狂按）"
    ENABLED_NEW_FUNC = f"by 吾峰起浪"

    WARNING_SIGN = "⚠️" if NEWER_VER else "?!"
    SURPRISE_SIGN = "✨" if NEWER_VER else "*"
    MUTEX_SIGN = "🔒" if NEWER_VER else "⚔"
    CFG_SIGN = "📝" if NEWER_VER else "❐"

