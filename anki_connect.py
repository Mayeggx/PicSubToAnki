import requests
import base64
from PIL import Image
from io import BytesIO
import threading
import os
import configparser  # 新增导入配置解析库

class AnkiConnect:
    def __init__(self, openai_client=None):
        self.openai_client = openai_client  # 接收OpenAI客户端实例
        self.folder_path = ""  # 图片文件夹路径（由main.py动态设置）
        self.voice_url = ""
        self.cards_name = ""
        self.mode = ""
        
        # 新增：读取Anki相关配置
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(__file__), "config.ini")  # 定位配置文件
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")
        config.read(config_path, encoding="utf-8")
        # 读取Anki相关配置（新增压缩参数）
        self.jp_deck = config.get("anki", "jp_deck")
        self.en_deck = config.get("anki", "en_deck")
        self.model_name = config.get("anki", "model_name")
        self.max_width = config.getint("anki", "max_width")  # 新增：读取最大宽度（整数）
        self.max_height = config.getint("anki", "max_height")  # 新增：读取最大高度（整数）
        self.image_quality = config.getint("anki", "image_quality")  # 新增：读取压缩质量（整数）


        self.fields = {
            "word": config.get("anki", "word_field"),
            "pronunciation": config.get("anki", "pronunciation_field"),
            "meaning": config.get("anki", "meaning_field"),
            "note": config.get("anki", "note_field"),
            "example": config.get("anki", "example_field"),
            "voice": config.get("anki", "voice_field")
        }


        self.set_mode('jp')  # 初始化默认模式

    def set_mode(self, newmode):
        self.mode = newmode
        # 修改：使用配置文件中的值
        if self.mode == 'jp':
            self.cards_name = self.jp_deck
        elif self.mode == 'en':
            self.cards_name = self.en_deck

    def make_voice_url(self, word, pronun):
        if (self.mode == 'jp'):
            return f'[sound:https://assets.languagepod101.com/dictionary/japanese/audiomp3.php?kanji={word}&kana={pronun}]'
        elif (self.mode == 'en'):
            return f'[sound:https://dict.youdao.com/dictvoice?audio={word}]'

    def anki_request(self, action, **params):
        """发送请求到AnkiConnect"""
        request_data = {
            'action': action,
            'version': 6,
            'params': params
        }
        try:
            response = requests.post('http://localhost:8765', json=request_data)
            return response.json()
        except Exception as e:
            print(f"连接错误: 无法连接Anki: {str(e)}")
            return None

    def store_media_file(self, filename):
        """将图片压缩为480p的jpg文件并存储到Anki媒体库"""
        img_path = os.path.join(self.folder_path, filename)
        base_name = os.path.splitext(filename)[0]
        compressed_filename = f"{base_name}.jpg"

        try:
            with Image.open(img_path) as img:
                # 修改：使用配置文件中的尺寸
                max_size = (self.max_width, self.max_height)
                img.thumbnail(max_size)

                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else img.split()[-1])
                    img = background
                else:
                    img = img.convert('RGB')

                img_buffer = BytesIO()
                # 修改：使用配置文件中的质量参数
                img.save(img_buffer, format='JPEG', quality=self.image_quality)
                img_data = img_buffer.getvalue()
                img_b64 = base64.b64encode(img_data).decode("utf-8")

                response = self.anki_request(
                    'storeMediaFile',
                    filename=compressed_filename,
                    data=img_b64
                )
                return {'filename': compressed_filename, 'response': response}
        except Exception as e:
            print(f"压缩或上传图片失败: {img_path} - {e}")
            return None

    def create_anki_card(self, filename, user_input, btn):
        """异步创建单张Anki卡片"""
        def async_task():
            if not self.openai_client:
                btn.config(state="normal", text="创建卡片")
                return

            raw_name = os.path.splitext(filename)[0]
            result = self.openai_client.explain_single(raw_name, user_input)
            if result['error']:
                btn.config(state="normal", text="创建卡片")
                return

            media_result = self.store_media_file(filename)
            if not media_result or media_result.get('response', {}).get('error'):
                btn.config(state="normal", text="创建卡片")
                return

            compressed_filename = media_result['filename']
            fields = {
                self.fields["word"]: result['word'],
                self.fields["pronunciation"]: result['pronunciation'],
                self.fields["meaning"]: result['meaning'],
                self.fields["note"]: result['note'],
                self.fields["example"]:  f'{result["example"]}<br><img src="{compressed_filename}">',
                self.fields["voice"]: self.make_voice_url(result['word'], result['pronunciation'])
            }

            note = {
                "deckName": self.cards_name,
                "modelName": self.model_name,
                "fields": fields,
                "options": {"allowDuplicate": True}
            }

            # 新增：查询是否存在相同word字段的卡片
            word_field = self.fields["word"]  # 获取配置中的word字段名（如"单词"）
            word_value = fields[word_field]   # 当前要添加的单词值
            # 构造Anki搜索查询（格式："字段名:字段值"）
            search_query = f'{word_field}:{word_value}'
            # 调用findNotes接口查询笔记ID
            search_response = self.anki_request('findNotes', query=search_query)
            print(f"查询[{word_value}]卡片响应: {search_response}")  # 打印查询结果

            # 新增：获取第一张卡片ID并更新例句字段
            if search_response and 'result' in search_response and search_response['result']:
                note_id = search_response['result'][0]  # 获取第一张卡片ID
                # 获取卡片详情
                get_note_response = self.anki_request('notesInfo', notes=[note_id])
                if get_note_response and not get_note_response.get('error') and 'result' in get_note_response:
                    current_note = get_note_response['result'][0]
                    # 提取原例句内容
                    current_example = current_note['fields'][self.fields["example"]]['value']
                    current_notes = current_note['fields'][self.fields["note"]]['value']
                    current_meaning = current_note['fields'][self.fields["meaning"]]['value']
                    # 拼接新例句（添加<br>分隔）
                    new_example = f"""{current_example}<br>2.{result["example"]}<br><img src="{compressed_filename}">"""
                    new_note = f"""{current_notes}<br>例句2含义：{result["note"]}"""
                    new_meaning = f"""{current_meaning}<br>{result["meaning"]}"""
                    # 更新例句字段
                    update_response = self.anki_request('updateNoteFields', note={
                        "id": note_id,
                        "fields": {self.fields["example"]: new_example,
                                   self.fields["note"]: new_note,
                                   self.fields["meaning"]: new_meaning}
                    })

                    if update_response and not update_response.get('error'):
                        print(f"成功更新卡片{note_id}的字段")
                        btn.config(bg='green', text='已更新')
                    else:
                        print(f"更新失败: {update_response.get('error') if update_response else '无响应'}")
                        btn.config(state="normal", text="更新失败")
                else:
                    print(f"获取卡片详情失败: {get_note_response.get('error') if get_note_response else '无响应'}")
                    btn.config(state="normal", text="更新失败")
            else:
                response = self.anki_request('addNote', note=note)
                print(f"成功创建卡片：{response['result']}")
                if response and not response.get('error'):
                    btn.config(bg='green', text='已创建')
                else:
                    btn.config(state="normal", text="创建失败")

        threading.Thread(target=async_task, daemon=True).start()

    def create_anki_cards(self, filenames, user_inputs, buttons):
        """异步批量创建Anki卡片"""
        def async_task():
            if len(filenames) != len(user_inputs) or len(filenames) != len(buttons):
                for btn in buttons:
                    btn.config(state="normal")
                return

            raw_names = [os.path.splitext(f)[0] for f in filenames]
            results = self.openai_client.explain_batch(raw_names, user_inputs) if self.openai_client else []

            success_count = 0
            for i, (filename, user_input, btn, result) in enumerate(zip(filenames, user_inputs, buttons, results)):
                if result.get('error'):
                    btn.config(text='创建失败')
                    continue

                media_result = self.store_media_file(filename)
                if not media_result or media_result.get('response', {}).get('error'):
                    btn.config(text='创建失败')
                    continue

                compressed_filename = media_result['filename']
                fields = {
                    self.fields["word"]: result['word'],
                    self.fields["pronunciation"]: result['pronunciation'],
                    self.fields["meaning"]: result['meaning'],
                    self.fields["note"]: result['note'],
                    self.fields["example"]: f'{result["example"]}<br><img src="{compressed_filename}">',
                    self.fields["voice"]: self.make_voice_url(result['word'], result['pronunciation'])
                }

                note_data = {
                    "deckName": self.cards_name,
                    "modelName": self.model_name,
                    "fields": fields,
                    "options": {"allowDuplicate": True}
                }

                # 新增：查询是否存在相同word字段的卡片
                word_field = self.fields["word"]  # 获取配置中的word字段名（如"单词"）
                word_value = fields[word_field]  # 当前要添加的单词值
                # 构造Anki搜索查询（格式："字段名:字段值"）
                search_query = f'{word_field}:{word_value}'
                # 调用findNotes接口查询笔记ID
                search_response = self.anki_request('findNotes', query=search_query)
                print(f"查询[{word_value}]卡片响应: {search_response}")  # 打印查询结果

                # 新增：获取第一张卡片ID并更新例句字段
                if search_response and 'result' in search_response and search_response['result']:
                    note_id = search_response['result'][0]  # 获取第一张卡片ID
                    # 获取卡片详情
                    get_note_response = self.anki_request('notesInfo', notes=[note_id])
                    if get_note_response and not get_note_response.get('error') and 'result' in get_note_response:
                        current_note = get_note_response['result'][0]
                        # 提取原例句内容
                        current_example = current_note['fields'][self.fields["example"]]['value']
                        current_notes = current_note['fields'][self.fields["note"]]['value']
                        current_meaning = current_note['fields'][self.fields["meaning"]]['value']
                        # 拼接新例句（添加<br>分隔）
                        new_example = f"""{current_example}<br>2.{result["example"]}<br><img src="{compressed_filename}">"""
                        new_note = f"""{current_notes}<br>例句2含义：{result["note"]}"""
                        new_meaning = f"""{current_meaning}<br>{result["meaning"]}"""
                        # 更新例句字段
                        update_response = self.anki_request('updateNoteFields', note={
                            "id": note_id,
                            "fields": {self.fields["example"]: new_example,
                                       self.fields["note"]: new_note,
                                       self.fields["meaning"]: new_meaning}
                        })

                        if update_response and not update_response.get('error'):
                            success_count += 1
                            print(f"成功更新卡片{note_id}的字段")
                            btn.config(bg='green', text='已更新')
                        else:
                            print(f"更新失败: {update_response.get('error') if update_response else '无响应'}")
                            btn.config(state="normal", text="更新失败")
                    else:
                        print(f"获取卡片详情失败: {get_note_response.get('error') if get_note_response else '无响应'}")
                        btn.config(state="normal", text="更新失败")
                else:
                    response = self.anki_request('addNote', note=note_data)
                    print(f"成功创建卡片：{response['result']}")
                    if response and not response.get('error'):
                        success_count += 1
                        btn.config(bg='green', text='已创建')
                    else:
                        btn.config(state="normal", text="创建失败")

            if success_count > 0:
                # 需通过main.py的root更新UI提示
                # 实际使用时需通过ImageViewerApp的root传递
                pass

        threading.Thread(target=async_task, daemon=True).start()