import json
from openai import OpenAI


class OpenAIExplanation:
    def __init__(self, api_key, base_url, model_name):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.mode = "jp"
        self.client = self._init_client()

    def _init_client(self):
        """初始化 OpenAI 客户端"""
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def construct_single_prompt_jp(self, subtitle, key):
        """构造单个查询的提示词"""
        return f"""请根据提供的单词返回以下结构化信息：
1. 日文单词原型（如果是变形，返回原形）
2. 日文的发音
3. 单词的日文释义（不包含单词本身，必须只有日文）
4. 当前的例句，并将和单词的部分用<b>{key}</b>的形式包围
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
}}
当前输入：
例句：{subtitle}
单词：{key}
请给出对应的输出"""

    def construct_single_prompt_en(self, subtitle, key):
            """构造单个查询的提示词"""
            return f"""请根据提供的单词返回以下结构化信息：
    1. 英文单词原型（如果是变形，返回原形）
    2. 单词的音标
    3. 单词的英文释义（不包含单词本身，必须只有英文）
    4. 当前的例句，并将和单词的部分用<b>{key}</b>的形式包围
    5. 用中文结合语境解释一下当前单词的意思

    示例输入：
    例句：The Demon Sword's wavelength seems to be......swelling
    单词：swelling
    （单词存在于例句之中）
    示例格式：
    {{
        "单词": "swell",
        "音标": "英[swel]美[swɛl]",
        "意义": "to expand or increase in intensity, size, or power, often implying a gradual or ominous buildup",
        "例句": "The Demon Sword's wavelength seems to be......<b>swelling</b>",
        "笔记": ""swelling" 在这里并非指物理上的“膨胀”，而是形容恶魔之剑的“波长”（可能指其能量波动或魔力）正在增强、扩大或变得不稳定。这暗示剑的力量在逐渐蓄积或失控，可能预示着即将爆发的危险或更强大的攻击性"
    }}
    当前输入：
    例句：{subtitle}
    单词：{key}
    请给出对应的输出"""

    def construct_batch_prompt_jp(self, pairs):
        """构造批量查询的提示词（多对subtitle和key）"""
        pair_descriptions = []
        for i, (subtitle, key) in enumerate(pairs):
            pair_descriptions.append(f"""
对{i + 1}:
例句：{subtitle}
单词：{key}
""")

        return f"""请根据提供的多组例句和单词，为每组返回以下结构化信息：
1. 日文单词原型（如果是变形，返回原形）
2. 日文的发音
3. 单词的日文释义（不包含单词本身，必须只有日文）
4. 对应的例句，并将单词部分用<b>原词</b>的形式包围
5. 用中文结合语境解释一下当前单词的意思

请为每个例句-单词对返回独立的JSON对象，用数组格式返回所有结果：
示例输入：
对1:
例句：連絡先 聞くの忘れたって わめいてたよ
单词：わめいて
对2:
例句：胸ぺッタンコのくせに
单词：胸
示例格式：
[
    {{
        "单词": "喚く",
        "音标": "わめく",
        "意义": "①大声でさけぶ。②騒ぎ立てる。"
        "例句": "連絡先 聞くの忘れたって　<b>わめいて</b>たよ"
        "笔记": "「わめいてた」是动词「わめく」（叫嚷、吵闹）的过去进行时，表示“（当时）在大声抱怨/嚷嚷”。句中指对方因忘记询问联系方式而焦急或生气地吵闹，带有责备或夸张语气。"
    }},
    {{
        "单词": "胸",
        "音标": "むね",
        "意义": "①人や動物の体の前面の一部分。乳房がある部分。②心の中。内面的な感情。",
        "例句": "<b>胸</b>ぺッタンコのくせに",
        "笔记": "「胸」在这里指的是胸部，特指人体上半身的前部区域，在这个例句中具体指向平坦的胸部（即没有丰满的乳房）。语境中可能带有一些调侃或自嘲的意味，描述胸部平坦的状态。"
    }}
]

需要分析的例句-单词对：
{"".join(pair_descriptions)}
"""

    def construct_batch_prompt_en(self, pairs):
            """构造批量查询的提示词（多对subtitle和key）"""
            pair_descriptions = []
            for i, (subtitle, key) in enumerate(pairs):
                pair_descriptions.append(f"""
    对{i + 1}:
    例句：{subtitle}
    单词：{key}
    """)

            return f"""请根据提供的多组例句和单词，为每组返回以下结构化信息：
    1. 英文单词原型（如果是变形，返回原形）
    2. 单词的音标
    3. 单词的英文释义（不包含单词本身，必须只有英文）
    4. 当前的例句，并将和单词的部分用<b>{key}</b>的形式包围
    5. 用中文结合语境解释一下当前单词的意思

    请为每个例句-单词对返回独立的JSON对象，用数组格式返回所有结果：
    示例输入：
    对1:
    例句：The Demon Sword's wavelength seems to be......swelling
    单词：swelling
    对2:
    例句：We don't want to overlook any dormant mines
    单词：dormant
    示例格式：
    [
        {{
            "单词": "swell",
            "音标": "英[swel]美[swɛl]",
            "意义": "to expand or increase in intensity, size, or power, often implying a gradual or ominous buildup",
            "例句": "The Demon Sword's wavelength seems to be......<b>swelling</b>",
            "笔记": "swelling在这里并非指物理上的“膨胀”，而是形容恶魔之剑的“波长”（可能指其能量波动或魔力）正在增强、扩大或变得不稳定。这暗示剑的力量在逐渐蓄积或失控，可能预示着即将爆发的危险或更强大的攻击性"
        }},
        {{
            "单词": "dormant",
            "音标": "英[ˈdɔ:mənt]美[ˈdɔrmənt]",
            "意义": "temporarily inactive or inactive for a period of time, but with the potential to become active again",
            "例句": "We don't want to overlook any <b>dormant</b> mines",
            "笔记": "dormant在这里形容矿井暂时处于不活跃或停用状态，但仍有潜在危险。这些矿井可能未被完全废弃，虽然表面上看似安全，但内部可能残留爆炸物、有毒气体或结构隐患（如塌方风险）。"
        }}
    ]

    需要分析的例句-单词对：
    {"".join(pair_descriptions)}
    """

    def parse_response(self, response_text):
        """解析响应文本，提取 JSON 数据"""
        try:
            # 处理可能的代码块格式（如 ```json...```）
            if response_text.startswith("```json") and response_text.endswith("```"):
                json_str = response_text[7:-3].strip()
            else:
                json_str = response_text.strip()

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析失败：{str(e)}")
            print(f"原始响应：{response_text}")
            return None

    def explain_single(self, subtitle, key):
        """调用 OpenAI API 解析单个单词信息"""
        try:
            if(self.mode == 'jp'):
                prompt = self.construct_single_prompt_jp(subtitle, key)
                language = "日语"
            elif(self.mode == 'en'):
                prompt = self.construct_single_prompt_en(subtitle, key)
                language = "英语"

            print(f"正在查询单词：{key}")

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": f"你是一个专业的{language}词典助手，能够准确返回单词信息的JSON格式数据"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                stream=False
            )

            response_text = response.choices[0].message.content.strip()
            print(f"收到原始响应：{response_text}")
            word_info = self.parse_response(response_text)

            if not word_info:
                return {"error": "响应解析失败"}

            return {
                "word": word_info.get("单词", ""),
                "pronunciation": word_info.get("音标", ""),
                "meaning": word_info.get("意义", ""),
                "example": word_info.get("例句", ""),
                "note": word_info.get("笔记", ""),
                "error": None
            }

        except Exception as e:
            print(f"API调用失败：{str(e)}")
            return {"error": f"API调用失败：{str(e)}"}

    def explain_batch(self, subtitles, keys):
        """调用 OpenAI API 批量解析多对subtitle和key"""
        if not subtitles or not keys or len(subtitles) != len(keys):
            raise ValueError("subtitles和keys必须是相同长度的非空列表")

        pairs = list(zip(subtitles, keys))

        try:
            if(self.mode == 'jp'):
                prompt = self.construct_batch_prompt_jp(pairs)
                language = "日语"
            elif(self.mode == 'en'):
                prompt = self.construct_batch_prompt_en(pairs)
                language = "英语"
            print(f"正在批量查询 {len(pairs)} 对单词")

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system",
                     "content": f"你是一个专业的{language}词典助手，能够准确返回多组单词信息的JSON格式数据数组"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                stream=False
            )

            response_text = response.choices[0].message.content.strip()
            print(f"收到批量响应：{response_text[:200]}...")
            results = self.parse_response(response_text)

            if not results:
                return [{"error": "批量响应解析失败"} for _ in pairs]

            # 确保返回结果数量与请求的单词数量一致
            formatted_results = []
            for i, (subtitle, key) in enumerate(pairs):
                if i < len(results) and isinstance(results[i], dict):
                    formatted_results.append({
                        "word": results[i].get("单词", ""),
                        "pronunciation": results[i].get("音标", ""),
                        "meaning": results[i].get("意义", ""),
                        "example": results[i].get("例句", ""),
                        "note": results[i].get("笔记", ""),
                        "error": None
                    })
                else:
                    formatted_results.append({"error": f"对 {subtitle} - {key} 的解析失败"})

            return formatted_results

        except Exception as e:
            print(f"批量API调用失败：{str(e)}")
            return [{"error": f"API调用失败：{str(e)}"} for _ in pairs]