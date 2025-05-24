import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import requests
import base64
import json
import threading  # 导入线程模块
import configparser  # 新增导入configparser模块
from openai_utils import OpenAIExplanation
from anki_connect import AnkiConnect  # 新增导入


class ImageViewerApp:
    def __init__(self, root):

        self.root = root
        self.root.title("图片字幕转Anki卡片")
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

        # 新增：全选按钮（在批量添加按钮右侧）
        self.select_all_btn = ttk.Button(self.toolbar, text="全选", command=self.select_all)
        self.select_all_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 新增：取消全选按钮（在全选按钮右侧）
        self.select_none_btn = ttk.Button(self.toolbar, text="取消全选", command=self.select_none)
        self.select_none_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 新增：切换模式按钮（在取消全选按钮右侧）
        self.toggle_mode_btn = ttk.Button(self.toolbar, text="切换模式", command=self.toggle_mode)
        self.toggle_mode_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # 新增：删除所有图片按钮（在切换模式按钮右侧）
        self.delete_btn = ttk.Button(self.toolbar, text="删除所有图片", command=self.delete_all_images)
        self.delete_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.anki_connect = AnkiConnect()  # 初始化AnkiConnect实例
        # 新增：模式显示标签（在切换模式按钮右侧）
        current_mode = self.anki_connect.mode
        mode_text = "日语模式" if current_mode == "jp" else "英语模式" if current_mode == "en" else "未知模式"
        self.mode_label = ttk.Label(self.toolbar, text=mode_text)
        self.mode_label.pack(side=tk.LEFT, padx=5, pady=5)

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

        # 从外置INI文件读取OpenAI配置（替换原硬编码）
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(__file__), "config.ini")  # 定位项目根目录的config.ini
        if not os.path.exists(config_path):
            messagebox.showerror("配置错误", f"未找到配置文件 {config_path}\n请按照文档创建配置文件")
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")
        config.read(config_path, encoding="utf-8")
        self.openai_config = {
            "api_key": config.get("openai", "api_key"),
            "base_url": config.get("openai", "base_url"),
            "model_name": config.get("openai", "model_name")
        }

        self.openai_client = None

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
        self.anki_connect.folder_path = self.folder_path
        if not self.folder_path:
            return

        valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
        image_files = [f for f in os.listdir(self.folder_path)
                       if os.path.splitext(f)[1].lower() in valid_extensions]

        # 修改列配置为5列（确认框+原4列）
        for i in range(5):
            self.content_frame.columnconfigure(i, weight=1, uniform="cols")

        # 新增：添加标题行（row=0）
        title_config = [
            ("确认框", 0),  # 列0：确认框标题
            ("图片", 1),  # 列1：图片标题
            ("文件名", 2),  # 列2：文件名标题
            ("单词", 3),  # 列3：单词输入框标题
            ("操作", 4)  # 列4：操作按钮标题
        ]
        for text, col in title_config:
            title_label = ttk.Label(
                self.content_frame,
                text=text,
                font=('微软雅黑', 10, 'bold'),  # 加粗字体更醒目
                anchor="center"  # 文字居中显示
            )
            title_label.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)

        # 调整图片行从row=1开始循环（原row从0开始，现改为start=1）
        for row, filename in enumerate(image_files, start=1):
            # 新增：确认框列（调整sticky参数为居中）
            check_var = tk.BooleanVar()
            self.check_vars.append(check_var)
            check_btn = ttk.Checkbutton(self.content_frame, variable=check_var)
            check_btn.grid(row=row, column=0, sticky="", padx=5, pady=5)  # 列0

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
            # 新增：绑定图片点击事件
            img_label.bind("<Button-1>", lambda event, path=img_path: self.open_image(path))
            img_label.grid(row=row, column=1, sticky="nsew", padx=5, pady=5)  # 列1

            # 原name_label（第三列）修改为可换行、可选中的Text组件（新增居中对齐）
            text_widget = tk.Text(
                self.content_frame,
                wrap="word",  # 按单词自动换行
                width=20,  # 宽度（约20个字符）
                height=3,  # 高度（最多3行）
                state="disabled",  # 只读状态
                bg="systembuttonface",  # 背景色与系统按钮一致
                bd=0,  # 无边框
                font=ttk.Style().lookup("TLabel", "font")  # 继承Label字体
            )
            # 插入文本时临时启用编辑状态
            text_widget.config(state="normal")
            text_widget.insert("1.0", filename)  # 在文本框开头插入文件名
            text_widget.config(state="disabled")  # 恢复只读状态
            text_widget.grid(row=row, column=2, sticky="nsew", padx=5, pady=5)  # 列2

            input_entry = ttk.Entry(self.content_frame)
            input_entry.grid(row=row, column=3, sticky="nsew", padx=5, pady=5)  # 列3（对应"单词"标题列）

            action_btn = tk.Button(
                self.content_frame,
                text="创建卡片",
                state="normal"
            )
            action_btn['command'] = lambda f=filename, e=input_entry, btn=action_btn: self.handle_button_click(f, e,
                                                                                                               btn)
            action_btn.grid(row=row, column=4, sticky="nsew", padx=5, pady=5)  # 列4（对应"操作"标题列）

            # 保存当前行信息（无需修改file_info，因为不影响后续逻辑）
            self.file_info.append((filename, input_entry, action_btn))

        self.content_frame.rowconfigure(len(image_files) + 1, weight=1)  # 调整行权重（标题行+文件行）

    def handle_button_click(self, filename, input_entry, btn):
        user_input = input_entry.get().strip()
        if not user_input:
            messagebox.showerror("输入错误", "请输入内容后再创建卡片")
            return

        btn.config(state="disabled")
        # 延迟初始化OpenAI客户端
        if not self.openai_client:
            print("第一次初始化OpenAI客户端")
            self.openai_client = OpenAIExplanation(**self.openai_config)
            self.anki_connect.openai_client = self.openai_client  # 传递给AnkiConnect

        self.anki_connect.create_anki_card(filename, user_input, btn)  # 调用新模块方法

    def batch_add_cards(self):
        selected = []
        for idx, check_var in enumerate(self.check_vars):
            if check_var.get() and idx < len(self.file_info):
                filename, input_entry, action_btn = self.file_info[idx]
                user_input = input_entry.get().strip()
                if not user_input:
                    messagebox.showerror("输入错误", f"第 {idx + 1} 行的输入内容不能为空")
                    return
                action_btn.config(state="disabled")
                selected.append((filename, user_input, action_btn))

        if not selected:
            messagebox.showinfo("提示", "请先选择需要批量添加的行")
            return

        filenames, user_inputs, buttons = zip(*selected)
        # 延迟初始化OpenAI客户端
        if not self.openai_client:
            print("第一次初始化OpenAI客户端")
            self.openai_client = OpenAIExplanation(**self.openai_config)
            self.anki_connect.openai_client = self.openai_client  # 传递给AnkiConnect

        self.anki_connect.create_anki_cards(filenames, user_inputs, buttons)  # 调用新模块方法

    def select_all(self):
        """一键勾选所有第一列确认框"""
        for check_var in self.check_vars:
            check_var.set(True)  # 设置为选中状态

    def select_none(self):
        """一键取消所有第一列确认框的勾选"""
        for check_var in self.check_vars:
            check_var.set(False)  # 设置为未选中状态

    # 新增：切换模式方法
    def toggle_mode(self):
        current_mode = self.anki_connect.mode
        new_mode = "en" if current_mode == "jp" else "jp"

        self.anki_connect.set_mode(new_mode)
        # 更新模式显示标签
        mode_text = "日语模式" if new_mode == "jp" else "英语模式"
        self.mode_label.config(text=mode_text)

        if not self.openai_client:
            print("第一次初始化OpenAI客户端")
            self.openai_client = OpenAIExplanation(**self.openai_config)
            self.anki_connect.openai_client = self.openai_client  # 传递给AnkiConnect
        self.openai_client.mode = new_mode

    def delete_all_images(self):
        """删除当前文件夹下所有支持的图片文件并更新视图"""
        if not self.folder_path:
            messagebox.showinfo("提示", "请先选择需要操作的文件夹")
            return

        # 二次确认删除
        confirm = messagebox.askyesno("危险操作",
                                      "确认要删除当前文件夹下的所有图片吗？\n（支持格式：.png, .jpg, .jpeg, .gif, .bmp）")
        if not confirm:
            return

        valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
        try:
            deleted_count = 0
            for filename in os.listdir(self.folder_path):
                file_path = os.path.join(self.folder_path, filename)
                # 仅删除文件且符合图片格式
                if os.path.isfile(file_path) and os.path.splitext(filename)[1].lower() in valid_extensions:
                    os.remove(file_path)
                    deleted_count += 1

            if deleted_count > 0:
                messagebox.showinfo("操作完成", f"已成功删除 {deleted_count} 张图片")
            else:
                messagebox.showinfo("操作完成", "当前文件夹下无支持的图片文件")

            # 清空并刷新视图（调用load_folder重新加载空文件夹）
            self.load_folder()

        except Exception as e:
            messagebox.showerror("删除失败", f"删除过程中发生错误：{str(e)}")

    # 新增：打开图片文件的方法
    def open_image(self, image_path):
        """使用系统默认程序打开图片文件"""
        os.startfile(image_path)


if __name__ == "__main__":
    root = tk.Tk()
    # 添加图标设置（新增代码）
    root.iconbitmap("app.ico")  # 路径为项目根目录下的app.ico文件
    app = ImageViewerApp(root)
    root.mainloop()