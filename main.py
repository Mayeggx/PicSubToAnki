import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import requests
import base64
import json
import threading  # 导入线程模块
from openai_utils import OpenAIExplanation


class ImageViewerApp:
    def __init__(self, root):


        self.root = root
        self.root.title("图片查看器")
        self.root.geometry("800x600")
        self.folder_path = ""  # 保存当前文件夹路径

        # 创建顶部工具栏
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(fill=tk.X)

        # 选择文件夹按钮（原代码）
        self.select_btn = ttk.Button(self.toolbar, text="选择文件夹", command=self.load_folder)
        self.select_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 新增：批量添加按钮（与选择文件夹按钮同一行，相邻放置）
        self.batch_btn = ttk.Button(self.toolbar, text="批量添加", command=self.batch_add_cards)
        self.batch_btn.pack(side=tk.LEFT, padx=5, pady=5)

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

        self.openai_config = {
            "api_key": "sk-dddfdbdf7ac747e2868af2a4fdb1346f",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model_name": "qwen-plus"
        }
        self.openai_client = None  # 初始化为None，延迟初始化

    def on_canvas_configure(self, event):
        self.canvas.itemconfig("frame", width=event.width)

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def load_folder(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self.file_info = []  # 清空历史记录
        self.check_vars = []  # 清空确认框状态

        self.folder_path = filedialog.askdirectory()  # 保存文件夹路径
        if not self.folder_path:
            return

        valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
        image_files = [f for f in os.listdir(self.folder_path)
                       if os.path.splitext(f)[1].lower() in valid_extensions]

        # 修改列配置为5列（确认框+原4列）
        for i in range(5):
            self.content_frame.columnconfigure(i, weight=1, uniform="cols")

        for row, filename in enumerate(image_files):
            # 新增：确认框列（调整sticky参数为居中）
            check_var = tk.BooleanVar()
            self.check_vars.append(check_var)
            check_btn = ttk.Checkbutton(self.content_frame, variable=check_var)
            check_btn.grid(row=row, column=0, sticky="", padx=5, pady=5)  # sticky改为空字符串实现居中

            # 原组件列号后移1位（0→1, 1→2, 2→3, 3→4）
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
            img_label.grid(row=row, column=1, sticky="nsew", padx=5, pady=5)  # 列号改为1

            # 原name_label（第三列）修改为可换行、可选中的Text组件（新增居中对齐）
            text_widget = tk.Text(
                self.content_frame,
                wrap="word",  # 按单词自动换行
                width=20,      # 宽度（约20个字符）
                height=3,      # 高度（最多3行）
                state="disabled",  # 只读状态
                bg="systembuttonface",  # 背景色与系统按钮一致
                bd=0,          # 无边框
                font=ttk.Style().lookup("TLabel", "font")  # 继承Label字体
            )
            # 插入文本时临时启用编辑状态
            text_widget.config(state="normal")
            text_widget.insert("1.0", filename)  # 在文本框开头插入文件名
            text_widget.config(state="disabled")  # 恢复只读状态
            text_widget.grid(row=row, column=2, sticky="nsew", padx=5, pady=5)  # 列号保持为2

            input_entry = ttk.Entry(self.content_frame)
            input_entry.grid(row=row, column=3, sticky="nsew", padx=5, pady=5)  # 列号改为3

            action_btn = tk.Button(
                self.content_frame,
                text="创建卡片",
                state="normal"
            )
            action_btn['command'] = lambda f=filename, e=input_entry, btn=action_btn: self.handle_button_click(f, e, btn)
            action_btn.grid(row=row, column=4, sticky="nsew", padx=5, pady=5)  # 列号改为4

            # 保存当前行信息（无需修改file_info，因为不影响后续逻辑）
            self.file_info.append( (filename, input_entry, action_btn) )

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
            # 延迟初始化OpenAI客户端（首次调用时初始化）
            if not self.openai_client:
                print("第一次初始化OpenAI客户端")
                self.openai_client = OpenAIExplanation(**self.openai_config)

            # 调用DeepSeek API解释文件名
            raw_name = os.path.splitext(filename)[0]
            result = self.openai_client.explain_single(raw_name, user_input)
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
                "例句": f'<img src="{compressed_filename}"><br>{example}',
                "发音": f'[sound:https://assets.languagepod101.com/dictionary/japanese/audiomp3.php?kanji={word}&kana={pronunciation}]'
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

    def create_anki_cards(self, filenames, user_inputs, buttons):
        """异步批量创建Anki卡片"""

        def async_task():
            # 验证输入列表长度一致
            if not filenames or len(filenames) != len(user_inputs) or len(filenames) != len(buttons):
                self.root.after(0, lambda: messagebox.showerror("输入错误", "文件名、用户输入和按钮数量必须一致"))
                for btn in buttons:
                    self.root.after(0, btn.config, {'state': 'normal'})
                return

            # 准备批量查询
            raw_names = [os.path.splitext(filename)[0] for filename in filenames]

            # 延迟初始化OpenAI客户端（首次调用时初始化）
            if not self.openai_client:
                print("第一次初始化OpenAI客户端")
                self.openai_client = OpenAIExplanation(**self.openai_config)

            # 调用批量API解析单词
            results = self.openai_client.explain_batch(raw_names, user_inputs)

            # 处理API结果
            success_count = 0
            for i, (filename, user_input, btn, result) in enumerate(zip(filenames, user_inputs, buttons, results)):
                if result.get('error'):
                    print(f"第 {i + 1} 个单词解析失败: {result['error']}")
                    # 保持按钮禁用，仅修改显示状态
                    self.root.after(0, btn.config, {'state': 'disabled', 'bg': 'systembuttonface', 'text': '创建失败'})
                    continue

                word = result['word']
                pronunciation = result['pronunciation']
                meaning = result['meaning']
                example = result['example']
                note = result['note']

                # 存储压缩后的图片到Anki
                media_result = self.store_media_file(filename)
                if not media_result or media_result.get('response') is None or media_result.get('response').get(
                        'error'):
                    error_msg = media_result.get('response').get('error') if media_result else "未知错误"
                    self.root.after(0, messagebox.showerror, "图片上传失败", f"无法上传图片: {error_msg}")
                    self.root.after(0, btn.config, {'state': 'normal', 'bg': 'systembuttonface', 'text': '创建失败'})
                    continue

                compressed_filename = media_result['filename']

                # 构建卡片内容
                fields = {
                    "单词": word,
                    "音标": pronunciation,
                    "释义": meaning,
                    "笔记": note,
                    "例句": f'<img src="{compressed_filename}"><br>{example}',
                    "发音": f'[sound:https://assets.languagepod101.com/dictionary/japanese/audiomp3.php?kanji={word}&kana={pronunciation}]'
                }

                # 创建笔记
                note_data = {
                    "deckName": "Default",
                    "modelName": "划词助手Antimoon模板",
                    "fields": fields,
                    "options": {
                        "allowDuplicate": False
                    }
                }

                response = self.anki_request('addNote', note=note_data)
                if response and not response.get('error'):
                    success_count += 1
                    # 保持按钮禁用，显示成功状态
                    self.root.after(0, btn.config, {'state': 'disabled', 'bg': 'green', 'text': '已创建'})
                else:
                    error = response.get('error') if response else "未知错误"
                    self.root.after(0, messagebox.showerror, "创建失败", f"无法创建卡片: {error}")
                    # 保持按钮禁用，显示失败状态
                    self.root.after(0, btn.config, {'state': 'disabled', 'bg': 'systembuttonface', 'text': '创建失败'})

            # 全部处理完成后显示摘要
            if success_count > 0:
                self.root.after(0, lambda: messagebox.showinfo("批量创建结果",
                                                               f"成功创建 {success_count}/{len(filenames)} 张卡片"))

        threading.Thread(target=async_task, daemon=True).start()

    def batch_add_cards(self):
        """处理批量添加按钮点击事件"""
        # 收集选中的行
        selected = []
        for idx, check_var in enumerate(self.check_vars):
            if check_var.get():  # 确认框被选中
                if idx >= len(self.file_info):  # 防止索引越界
                    continue
                filename, input_entry, action_btn = self.file_info[idx]
                user_input = input_entry.get().strip()
                if not user_input:
                    messagebox.showerror("输入错误", f"第 {idx+1} 行的输入内容不能为空")
                    return
                # 立即禁用选中的按钮，防止重复提交
                action_btn.config(state="disabled")
                selected.append( (filename, user_input, action_btn) )

        if not selected:
            messagebox.showinfo("提示", "请先选择需要批量添加的行")
            return

        # 提取参数并调用批量创建函数
        filenames = [f for f, _, _ in selected]
        user_inputs = [u for _, u, _ in selected]
        buttons = [b for _, _, b in selected]
        self.create_anki_cards(filenames, user_inputs, buttons)


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageViewerApp(root)
    root.mainloop()