import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import requests
import base64
import json
import threading  # 导入线程模块


class ImageViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片查看器")
        self.root.geometry("800x600")
        self.folder_path = ""  # 保存当前文件夹路径

        # 创建顶部工具栏
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(fill=tk.X)

        self.select_btn = ttk.Button(self.toolbar, text="选择文件夹", command=self.load_folder)
        self.select_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 创建主内容区域
        self.canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.content_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.content_frame, anchor=tk.NW)

        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.content_frame.bind("<Configure>", self.on_frame_configure)

        for i in range(4):
            self.content_frame.columnconfigure(i, weight=1, uniform="cols")

    def on_canvas_configure(self, event):
        self.canvas.itemconfig("frame", width=event.width)

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def load_folder(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.folder_path = filedialog.askdirectory()  # 保存文件夹路径
        if not self.folder_path:
            return

        valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
        image_files = [f for f in os.listdir(self.folder_path)
                       if os.path.splitext(f)[1].lower() in valid_extensions]

        for row, filename in enumerate(image_files):
            img_path = os.path.join(self.folder_path, filename)

            try:
                with Image.open(img_path) as img:
                    img.thumbnail((100, 100))
                    tk_img = ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"无法加载图片: {img_path} - {e}")
                continue

            img_label = ttk.Label(self.content_frame, image=tk_img)
            img_label.image = tk_img
            img_label.grid(row=row, column=0, sticky="nsew", padx=5, pady=5)

            name_entry = ttk.Entry(self.content_frame)
            name_entry.insert(0, filename)
            name_entry.config(state="readonly")
            name_entry.grid(row=row, column=1, sticky="nsew", padx=5, pady=5)

            input_entry = ttk.Entry(self.content_frame)
            input_entry.grid(row=row, column=2, sticky="nsew", padx=5, pady=5)

            # 修改为tk.Button以便直接设置背景色（ttk.Button样式控制复杂）
            action_btn = tk.Button(
                self.content_frame,
                text="创建卡片",
                state="normal"  # 初始状态为可用
            )
            # 使用默认参数绑定当前按钮对象到lambda，并传递input_entry
            action_btn['command'] = lambda f=filename, e=input_entry, btn=action_btn: self.handle_button_click(f, e,
                                                                                                               btn)
            action_btn.grid(row=row, column=3, sticky="nsew", padx=5, pady=5)

        self.content_frame.rowconfigure(len(image_files), weight=1)

    def handle_button_click(self, filename, input_entry, btn):
        """按钮点击处理函数：验证输入并启动线程"""
        user_input = input_entry.get().strip()
        if not user_input:
            messagebox.showerror("输入错误", "请输入内容后再创建卡片")
            return  # 阻止任务执行

        btn.config(state="disabled")  # 输入有效时禁用按钮
        threading.Thread(
            target=self.create_anki_card,
            args=(filename, user_input, btn),
            daemon=True
        ).start()

    def anki_request(self, action, **params):
        """发送请求到AnkiConnect"""
        request_data = json.dumps({
            'action': action,
            'version': 6,
            'params': params
        })
        try:
            response = requests.post('http://localhost:8765', data=request_data)
            return json.loads(response.text)
        except Exception as e:
            messagebox.showerror("连接错误", f"无法连接Anki: {str(e)}")
            return None

    def store_media_file(self, filename):
        """将图片压缩为480p的jpg文件并存储到Anki媒体库"""
        img_path = os.path.join(self.folder_path, filename)
        base_name = os.path.splitext(filename)[0]
        compressed_filename = f"{base_name}.jpg"  # 生成新的jpg文件名

        try:
            with Image.open(img_path) as img:
                # 调整尺寸为480p（最大高度480，保持宽高比）
                max_size = (320, 240)  # 480p常见分辨率854x480
                img.thumbnail(max_size)

                # 转换为RGB模式（处理RGBA图片）
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else img.split()[-1])
                    img = background
                else:
                    img = img.convert('RGB')

                # 保存到内存中的BytesIO
                from io import BytesIO
                img_buffer = BytesIO()
                img.save(img_buffer, format='JPEG', quality=40)  # 调整质量参数
                img_data = img_buffer.getvalue()

                # base64编码
                img_b64 = base64.b64encode(img_data).decode("utf-8")

                # 上传到Anki
                response = self.anki_request(
                    'storeMediaFile',
                    filename=compressed_filename,
                    data=img_b64
                )
                return {'filename': compressed_filename, 'response': response}
        except Exception as e:
            print(f"压缩或上传图片失败: {img_path} - {e}")
            return None

    def create_anki_card(self, filename, user_input, btn):  # 新增按钮参数
        """异步创建Anki卡片（使用压缩后的图片+文件名解释）"""

        def async_task():
            # 调用DeepSeek API解释文件名
            raw_name = os.path.splitext(filename)[0]
            result = self.explain(raw_name, user_input)
            if result['error']:
                print("返回失败")
                # 操作失败时恢复按钮状态
                self.root.after(0, btn.config, {'state': 'normal', 'bg': 'systembuttonface', 'text': '创建卡片'})
                return

            word = result['word']
            pronunciation = result['pronunciation']
            meaning = result['meaning']
            example = result['example']
            note = result['note']

            # 存储压缩后的图片到Anki
            media_result = self.store_media_file(filename)
            if not media_result or media_result.get('response') is None or media_result.get('response').get('error'):
                error_msg = media_result.get('response').get('error') if media_result else "未知错误"
                self.root.after(0, messagebox.showerror, "图片上传失败", f"无法上传图片: {error_msg}")
                # 操作失败时恢复按钮状态
                self.root.after(0, btn.config, {'state': 'normal', 'bg': 'systembuttonface', 'text': '创建卡片'})
                return

            compressed_filename = media_result['filename']

            # 构建卡片内容（使用压缩后的jpg文件名）
            fields = {
                "单词": word,
                "音标": pronunciation,
                "释义": meaning,
                "笔记": note,
                "例句": f'<img src="{compressed_filename}"><br>{example}'
            }

            # 创建笔记
            note = {
                "deckName": "Default",
                "modelName": "划词助手Antimoon模板",
                "fields": fields,
                "options": {
                    "allowDuplicate": False
                }
            }

            response = self.anki_request('addNote', note=note)
            if response and not response.get('error'):
                # 成功时修改按钮样式（保持禁用状态，仅改变视觉反馈）
                self.root.after(0, btn.config, {'bg': 'green', 'text': '已创建'})
            else:
                error = response.get('error') if response else "未知错误"
                self.root.after(0, messagebox.showerror, "创建失败", f"无法创建卡片: {error}")
                # 操作失败时恢复按钮状态
                self.root.after(0, btn.config, {'state': 'normal', 'bg': 'systembuttonface', 'text': '创建卡片'})

        threading.Thread(target=async_task, daemon=True).start()

    def explain(self, subtitle, key):
        """使用DeepSeek API查询单词信息并返回结构化数据"""
        import openai
        from openai import OpenAI
        import json

        # 初始化返回结构
        result = {
            "单词": "",
            "音标": "",
            "意义": "",
            "错误": None
        }

        client = OpenAI(
            api_key="sk-5be20fcb377042bb9788055b7e24787a",
            base_url="https://api.deepseek.com"
        )

        try:
            # 构造精准提示词
            prompt = f"""请根据提供的单词返回以下结构化信息：
    1. 日文单词原型（如果是变形，返回原形）
    2. 日文的发音
    3. 日文的释义（不包含单词本身）
    4. 当前的例句，并将和单词的部分用<b>key</b>的形式包围
    5. 用中文结合语境解释一下当前单词的意思

    示例输入：
    例句：連絡先 聞くの忘れたって わめいてたよ
    单词：わめいて
    （单词存在于例句之中）
    示例格式：
    {{
        "单词": "喚く",
        "音标": "わめく",
        "意义": "①大声でさけぶ。②騒ぎ立てる。"
        "例句": "連絡先 聞くの忘れたって　<b>わめいて</b>たよ"
        "笔记": "「わめいてた」是动词「わめく」（叫嚷、吵闹）的过去进行时，表示“（当时）在大声抱怨/嚷嚷”。句中指对方因忘记询问联系方式而焦急或生气地吵闹，带有责备或夸张语气。"
        "发音": f'[sound:https://assets.languagepod101.com/dictionary/japanese/audiomp3.php?kanji={word}&kana={pronunciation}]'
    }}
    当前输入：
    例句：{subtitle}
    单词：{key}
    请给出对应的输出"""

            print(f"正在查询单词：{key}")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的日语词典助手，能够准确返回单词信息的JSON格式数据"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                stream=False
            )

            # 解析响应内容
            response_text = response.choices[0].message.content.strip()
            print(f"收到原始响应：{response_text}")

            # 尝试提取JSON内容（处理可能的代码块格式）
            json_str = response_text.split("```json")[-1].split("```")[0].strip()
            word_info = json.loads(json_str)

            # 提取字段
            result["单词"] = word_info.get("单词", "")
            result["音标"] = word_info.get("音标", "")
            result["意义"] = word_info.get("意义", "")
            result["例句"] = word_info.get("例句", "")
            result["笔记"] = word_info.get("笔记", "")

        except json.JSONDecodeError as e:
            error_msg = f"JSON解析失败：{str(e)}"
            print(error_msg)
            result["错误"] = error_msg
        except KeyError as e:
            error_msg = f"缺少必要字段：{str(e)}"
            print(error_msg)
            result["错误"] = error_msg
        except Exception as e:
            error_msg = f"API调用失败：{str(e)}"
            print(error_msg)
            result["错误"] = error_msg

        # 记录到变量（根据调用需求选择以下任一方式）
        word = result["单词"]
        pronunce = result["音标"]
        meaning = result["意义"]
        example = result["例句"]
        note = result["笔记"]

        # 返回结构化的数据
        return {
            "word": word,
            "pronunciation": pronunce,
            "meaning": meaning,
            "example": example,
            "note": note,
            "error": result["错误"]
        }


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageViewerApp(root)
    root.mainloop()