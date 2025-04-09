# -*- coding: utf-8 -*- # Ensure UTF-8 encoding for wider character support

import json
import re
import logging
from .base import DialogueAgent

class InitialDialogueAgent(DialogueAgent):
    """
    Agent 1: 初始对话生成代理
    接收对话背景、模式、目标、语言要求、难度和对话轮数，生成结构化对话
    """
    def __init__(self, client, model="o3-mini", api_type="openai"):
        super().__init__(client, model, api_type)
        self.agent_type = "initial_dialogue"
        self.description = "初始对话生成代理"
    
    def process(self, context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary="", custom_sentence=""):
        """
        处理输入参数并生成初始对话内容
        
        Args:
            context (str): 对话背景
            dialogue_mode (str): 对话模式 (AI先说/用户先说)
            goal (str): 对话目标
            language (str): 语言要求
            difficulty (str): 内容难度
            num_turns (int): 对话轮数
            custom_vocabulary (str): 自定义单词，可为空
            custom_sentence (str): 自定义句型，可为空
            
        Returns:
            dict: 包含原始文本、关键点、意图、关键情节词汇和关键情节句型的结构化对话数据
        """
        return self.generate_dialogue(context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary, custom_sentence)
    
    def generate_dialogue(self, context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary="", custom_sentence=""):
        """生成初始对话内容，采用优化策略"""
        # 设置最大尝试次数
        max_attempts = 3
        attempt = 0
        
        # 如果轮数较多，使用渐进式生成
        if num_turns > 5:
            return self._progressive_generate_dialogue(context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary, custom_sentence)
        
        while attempt < max_attempts:
            attempt += 1
            prompt = self._build_generation_prompt(context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary, custom_sentence)
            response = self.call_llm_api(prompt)
            
            try:
                # 尝试解析响应为 JSON 格式
                if response and '{' in response and '}' in response:
                    # 提取 JSON 部分
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    json_str = response[json_start:json_end]
                    dialogue_data = json.loads(json_str)
                    
                    # 验证对话并尝试修复
                    if "original_text" in dialogue_data:
                        original_text = dialogue_data["original_text"]
                        validate_result = self._validate_dialogue(original_text, dialogue_mode, num_turns)
                        
                        if validate_result["is_valid"]:
                            # 对话格式正确且轮数一致，直接返回
                            # 确保返回的数据包含所有必要字段
                            if "key_vocabulary" not in dialogue_data:
                                dialogue_data["key_vocabulary"] = []
                            if "key_sentences" not in dialogue_data:
                                dialogue_data["key_sentences"] = []
                            return dialogue_data
                        elif validate_result["can_fix"] and attempt < max_attempts:
                            # 尝试修复对话
                            fixed_dialogue = self._fix_dialogue(dialogue_data, validate_result, dialogue_mode, num_turns, context, goal)
                            if fixed_dialogue:
                                # 确保修复后的对话也包含新字段
                                if "key_vocabulary" not in fixed_dialogue:
                                    fixed_dialogue["key_vocabulary"] = []
                                if "key_sentences" not in fixed_dialogue:
                                    fixed_dialogue["key_sentences"] = []
                                return fixed_dialogue
                        elif attempt == max_attempts:
                            # 最后一次尝试，如果轮数相差不超过1，接受结果
                            actual_turns = validate_result.get("actual_turns", 0)
                            if abs(actual_turns - num_turns) <= 1:
                                logging.warning(f"接受不完全匹配的对话：要求{num_turns}轮，实际{actual_turns}轮。")
                                # 确保返回的数据包含所有必要字段
                                if "key_vocabulary" not in dialogue_data:
                                    dialogue_data["key_vocabulary"] = []
                                if "key_sentences" not in dialogue_data:
                                    dialogue_data["key_sentences"] = []
                                return dialogue_data
                else:
                    # 如果不是 JSON 格式，第三次尝试时接受原始内容
                    if attempt == max_attempts:
                        dialogue_data = {
                            "original_text": response,
                            "key_points": [],
                            "intentions": [],
                            "key_vocabulary": [],
                            "key_sentences": []
                        }
                        return dialogue_data
            except json.JSONDecodeError:
                # JSON 解析失败，第三次尝试时接受原始内容
                if attempt == max_attempts:
                    return {
                        "original_text": response,
                        "key_points": [],
                        "intentions": [],
                        "key_vocabulary": [],
                        "key_sentences": []
                    }
        
        # 如果所有尝试都失败，返回最基本的对话
        return self._create_fallback_dialogue(dialogue_mode, num_turns)
        
    def _validate_dialogue(self, dialogue_text, dialogue_mode, required_turns):
        """验证对话格式和轮数，并确定是否可以修复"""
        lines = dialogue_text.split('\n')
        # 过滤空行和非对话行
        dialogue_lines = [line.strip() for line in lines if line.strip() and 
                         (line.strip().startswith("A:") or line.strip().startswith("A ") or 
                          line.strip().startswith("B:") or line.strip().startswith("B "))]
        
        # 检查第一个说话者
        first_speaker = None
        for line in dialogue_lines:
            if line.startswith("A:") or line.startswith("A "):
                first_speaker = "A"
                break
            elif line.startswith("B:") or line.startswith("B "):
                first_speaker = "B"
                break
                
        correct_first_speaker = "B" if dialogue_mode == "AI先说" else "A"
        first_speaker_correct = (first_speaker == correct_first_speaker)
        
        # 计算轮数
        speaker_sequence = []
        for line in dialogue_lines:
            if line.startswith("A:") or line.strip().startswith("A "):
                speaker_sequence.append("A")
            elif line.startswith("B:") or line.startswith("B "):
                speaker_sequence.append("B")
        
        # 计算完整的轮数
        turns = 0
        i = 0
        while i < len(speaker_sequence) - 1:
            # 考虑两种对话模式
            if dialogue_mode == "AI先说":
                # B说完A说算一轮
                if speaker_sequence[i] == "B" and speaker_sequence[i+1] == "A":
                    turns += 1
                    i += 2  # 跳过已计算的两个说话者
                else:
                    i += 1  # 继续检查下一个
            else:  # 用户先说
                # A说完B说算一轮
                if speaker_sequence[i] == "A" and speaker_sequence[i+1] == "B":
                    turns += 1
                    i += 2
                else:
                    i += 1
        
        # 判断是否可以修复
        # 1. 轮数差距不超过2轮
        # 2. 第一个说话者正确
        can_fix = (abs(turns - required_turns) <= 2 and first_speaker_correct)
        
        return {
            "is_valid": turns == required_turns and first_speaker_correct,
            "actual_turns": turns,
            "expected_turns": required_turns,
            "first_speaker_correct": first_speaker_correct,
            "speaker_sequence": speaker_sequence,
            "can_fix": can_fix
        }
        
    def _fix_dialogue(self, dialogue_data, validation_result, dialogue_mode, num_turns, context, goal):
        """根据验证结果修复对话，而不是完全重新生成"""
        actual_turns = validation_result["actual_turns"]
        
        if actual_turns < num_turns:
            # 需要增加轮数
            return self._extend_dialogue(dialogue_data, dialogue_mode, num_turns - actual_turns, context, goal)
        elif actual_turns > num_turns:
            # 需要减少轮数
            return self._trim_dialogue(dialogue_data, dialogue_mode, num_turns)
        elif not validation_result["first_speaker_correct"]:
            # 第一个说话者不正确，需要调整
            return self._fix_first_speaker(dialogue_data, dialogue_mode)
        
        return None  # 无法修复
    
    def _extend_dialogue(self, dialogue_data, dialogue_mode, additional_turns, context, goal):
        """扩展对话，增加指定的轮数"""
        original_text = dialogue_data.get("original_text", "")
        key_points = dialogue_data.get("key_points", [])
        intentions = dialogue_data.get("intentions", [])
        
        # 构建提示，要求继续对话
        prompt = f"""
        请基于现有对话继续生成额外的 {additional_turns} 轮对话。
        
        原始对话背景: {context}
        对话目标: {goal}
        
        已有对话:
        {original_text}
        
        关键点:
        {', '.join(key_points)}
        
        对话意图:
        {', '.join(intentions)}
        
        请生成额外的 {additional_turns} 轮对话，保持与原有对话风格和目标一致。
        在对话中，请使用A代表用户，B代表AI/助手。
        一轮对话指的是用户和AI各说一次话。
        
        请只返回额外的对话内容，不需要重复已有对话。
        """
        
        extension_response = self.call_llm_api(prompt)
        
        # 合并原始对话和扩展部分
        if extension_response:
            # 确保原始对话结尾有换行
            if not original_text.endswith('\n'):
                original_text += '\n'
                
            # 合并对话
            new_text = original_text + extension_response
            
            # 更新对话数据
            dialogue_data["original_text"] = new_text
            return dialogue_data
            
        return None
    
    def _trim_dialogue(self, dialogue_data, dialogue_mode, required_turns):
        """修剪对话，减少到指定的轮数"""
        original_text = dialogue_data.get("original_text", "")
        lines = original_text.split('\n')
        
        # 提取对话行
        dialogue_lines = [line for line in lines if line.strip() and 
                         (line.strip().startswith("A:") or line.strip().startswith("A ") or 
                          line.strip().startswith("B:") or line.strip().startswith("B "))]
        
        # 根据对话模式确定如何计算轮数终点
        total_lines = 2 * required_turns  # 每轮两行：A和B各一行
        if dialogue_mode == "AI先说":  # B先说，以B-A为一轮
            trimmed_lines = dialogue_lines[:total_lines]
        else:  # A先说，以A-B为一轮
            trimmed_lines = dialogue_lines[:total_lines]
            
        # 重建对话文本
        trimmed_text = '\n'.join(trimmed_lines)
        dialogue_data["original_text"] = trimmed_text
        
        return dialogue_data
    
    def _fix_first_speaker(self, dialogue_data, dialogue_mode):
        """修复对话的第一个说话者"""
        # 由于修复第一个说话者可能会影响整个对话的连贯性，这里选择不进行修复
        # 而是依赖重新生成机制
        return None
    
    def _create_fallback_dialogue(self, dialogue_mode, num_turns):
        """创建一个基本的对话作为后备方案"""
        dialogue_text = ""
        
        # 根据对话模式确定谁先说话
        first_speaker = "B" if dialogue_mode == "AI先说" else "A"
        second_speaker = "A" if first_speaker == "B" else "B"
        
        for i in range(num_turns):
            dialogue_text += f"{first_speaker}: [本轮对话内容]\n"
            dialogue_text += f"{second_speaker}: [本轮对话回应]\n\n"
        
        return {
            "original_text": dialogue_text,
            "key_points": ["对话生成失败，使用了后备方案"],
            "intentions": ["完成指定轮数的对话基本框架"],
            "key_vocabulary": [],
            "key_sentences": []
        }
    
    def _progressive_generate_dialogue(self, context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary="", custom_sentence=""):
        """渐进式生成对话，适合轮数较多的情况"""
        # 每批次生成的轮数
        batch_size = 3
        
        # 初始化对话数据
        complete_dialogue = {
            "original_text": "",
            "key_points": [],
            "intentions": [],
            "key_vocabulary": [],
            "key_sentences": []
        }
        
        # 已生成的轮数
        generated_turns = 0
        
        # 第一批次生成
        first_batch_turns = min(batch_size, num_turns)
        prompt = self._build_generation_prompt(context, dialogue_mode, goal, language, difficulty, first_batch_turns, custom_vocabulary, custom_sentence)
        response = self.call_llm_api(prompt)
        
        try:
            # 解析第一批次响应
            if response and '{' in response and '}' in response:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                json_str = response[json_start:json_end]
                dialogue_data = json.loads(json_str)
                
                if "original_text" in dialogue_data:
                    # 验证第一批次对话
                    validate_result = self._validate_dialogue(dialogue_data["original_text"], dialogue_mode, first_batch_turns)
                    
                    if validate_result["is_valid"] or (abs(validate_result["actual_turns"] - first_batch_turns) <= 1):
                        # 接受第一批次对话
                        complete_dialogue["original_text"] = dialogue_data["original_text"]
                        complete_dialogue["key_points"] = dialogue_data.get("key_points", [])
                        complete_dialogue["intentions"] = dialogue_data.get("intentions", [])
                        complete_dialogue["key_vocabulary"] = dialogue_data.get("key_vocabulary", [])
                        complete_dialogue["key_sentences"] = dialogue_data.get("key_sentences", [])
                        generated_turns = validate_result["actual_turns"]
                    else:
                        # 第一批次生成失败，退回到常规方法
                        return self.generate_dialogue(context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary, custom_sentence)
                else:
                    # 解析失败，退回到常规方法
                    return self.generate_dialogue(context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary, custom_sentence)
            else:
                # 响应格式不正确，退回到常规方法
                return self.generate_dialogue(context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary, custom_sentence)
                
            # 如果已经生成了足够的轮数，返回结果
            if generated_turns >= num_turns:
                return complete_dialogue
                
            # 继续生成剩余的对话
            remaining_turns = num_turns - generated_turns
            
            while remaining_turns > 0:
                # 确定本批次需要生成的轮数
                current_batch_turns = min(batch_size, remaining_turns)
                
                # 获取对话的最后部分作为上下文
                dialogue_lines = complete_dialogue["original_text"].split('\n')
                context_lines = dialogue_lines[-min(4, len(dialogue_lines)):]  # 取最后4行或更少
                continuation_context = '\n'.join(context_lines)
                
                # 构建继续生成的提示
                extension_prompt = f"""
                请继续以下对话，生成额外的 {current_batch_turns} 轮对话。
                
                对话背景: {context}
                对话目标: {goal}
                
                对话的前面部分已经生成，以下是最近的对话内容:
                {continuation_context}
                
                请继续生成 {current_batch_turns} 轮对话，保持与前面对话的一致性和连贯性。
                在对话中，请使用A代表用户，B代表AI/助手。
                一轮对话指的是用户和AI各说一次话。
                
                请只返回新生成的对话部分，不需要重复前面的对话。
                """
                
                extension_response = self.call_llm_api(extension_prompt)
                
                # 解析和验证扩展部分
                if extension_response:
                    # 确保原始对话结尾有换行
                    if not complete_dialogue["original_text"].endswith('\n'):
                        complete_dialogue["original_text"] += '\n'
                        
                    # 合并对话
                    complete_dialogue["original_text"] += extension_response
                    
                    # 验证新增部分
                    validate_result = self._validate_dialogue(extension_response, dialogue_mode, current_batch_turns)
                    actual_batch_turns = validate_result["actual_turns"]
                    
                    # 更新已生成的轮数和剩余轮数
                    generated_turns += actual_batch_turns
                    remaining_turns = num_turns - generated_turns
                    
                    # 如果生成的轮数有显著偏差，退出循环避免无限生成
                    if actual_batch_turns < current_batch_turns / 2:
                        break
                else:
                    # 扩展失败，退出循环
                    break
            
            # 最终验证整个对话
            final_validation = self._validate_dialogue(complete_dialogue["original_text"], dialogue_mode, num_turns)
            
            # 如果轮数不符合要求但相差不大，接受结果
            if not final_validation["is_valid"] and abs(final_validation["actual_turns"] - num_turns) <= 1:
                logging.warning(f"渐进式生成接受近似结果：要求{num_turns}轮，实际{final_validation['actual_turns']}轮。")
                
            return complete_dialogue
                
        except Exception as e:
            logging.error(f"渐进式生成失败: {str(e)}")
            # 出错时退回到常规方法
            return self.generate_dialogue(context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary, custom_sentence)

    def _build_generation_prompt(self, context, dialogue_mode, goal, language, difficulty, num_turns, custom_vocabulary="", custom_sentence=""):
        """构建用于生成对话的提示"""
        # 确定谁先说话的说明
        first_speaker_instruction = ""
        if dialogue_mode == "AI先说":
            first_speaker_instruction = "请确保对话是由AI/助手先开始说话，而不是用户先说话。"
        elif dialogue_mode == "用户先说":
            first_speaker_instruction = "请确保对话是由用户先开始说话，而不是AI/助手先说话。"
            
        # 构建轮数示例
        turns_example = ""
        for i in range(1, num_turns + 1):
            if dialogue_mode == "AI先说":
                turns_example += f"轮次 {i}:\nB: [AI的对话]\nA: [用户的对话]\n\n"
            else:
                turns_example += f"轮次 {i}:\nA: [用户的对话]\nB: [AI的对话]\n\n"
        
        # 添加自定义单词和句型的说明
        custom_content = ""
        if custom_vocabulary:
            custom_content += f"\n请在对话中自然地融入以下单词: {custom_vocabulary}"
        if custom_sentence:
            custom_content += f"\n请在对话中自然地使用以下句型: {custom_sentence}"
        
        prompt = f"""
        作为一个专业的对话生成 AI，请根据以下要求创建一段对话：

        对话背景: {context}
        对话模式: {dialogue_mode}
        对话目标: {goal}
        语言要求: {language}
        内容难度: {difficulty}
        对话轮数: {num_turns}轮
        {custom_content}

        {first_speaker_instruction}
        
        在对话中，请使用A代表用户，B代表AI/助手。
        如果对话模式是"AI先说"，请确保B（AI/助手）是第一个说话的人。
        如果对话模式是"用户先说"，请确保A（用户）是第一个说话的人。
        
        请严格生成 {num_turns} 轮对话，其中一轮定义为用户和AI各说一次。
        对话结构应该遵循以下格式:
        
{turns_example}
        请注意:
        1. 生成的对话必须严格包含 {num_turns} 轮
        2. 每轮必须包含用户(A)和AI(B)各说一次
        3. 请确保按照{dialogue_mode}的设置确定第一个说话的角色

        请生成一段自然流畅的对话，包含以下内容并以 JSON 格式返回:
        1. 对话原始文本
        2. 情节关键节点
        3. 关键情节词汇（重要词汇，如专业术语或特定单词）
        4. 关键情节句型（重要句型，如特定的语法结构或表达方式）
        5. 对话中隐含的意图与目标

        返回格式示例:
        {{
            "original_text": "对话原始文本",
            "key_points": ["关键点1", "关键点2"],
            "key_vocabulary": ["关键词1", "关键词2"],
            "key_sentences": ["关键句型1", "关键句型2"],
            "intentions": ["意图1", "意图2"]
        }}
        """
        return prompt


class StyleAdaptationAgent(DialogueAgent):
    """
    Agent 2: 对话风格改编代理
    接收 Agent 1 的结构化对话数据和角色特质，生成风格化对话
    """
    def __init__(self, client, model="o3-mini", api_type="openai"):
        super().__init__(client, model, api_type)
        self.agent_type = "style_adaptation"
        self.description = "对话风格改编代理"
    
    def process(self, dialogue_data, user_traits_chara="", user_traits_address="", user_traits_custom="", 
               ai_traits_chara="", ai_traits_mantra="", ai_traits_tone="", ai_emo="", ai_emo_mode="自动模式", 
               language=None, user_traits=None, ai_traits=None):
        """
        处理输入参数并生成风格化对话
        
        Args:
            dialogue_data (dict): Agent 1 生成的结构化对话数据
            user_traits_chara (str): 用户性格特质
            user_traits_address (str): 他人对用户的称呼
            user_traits_custom (str): 用户自定义特质
            ai_traits_chara (str): AI性格特质
            ai_traits_mantra (str): AI口头禅
            ai_traits_tone (str): AI语气
            ai_emo (str): AI动作或神态描述语（当ai_emo_mode为"自定义模式"时有效）
            ai_emo_mode (str): AI动作/表情描述模式，"自动模式"或"自定义模式"
            language (str, optional): 输出语言
            user_traits (str, optional): 兼容V1版本的用户特质（如果提供了详细特质，此项可忽略）
            ai_traits (str, optional): 兼容V1版本的AI特质（如果提供了详细特质，此项可忽略）
            
        Returns:
            str: 风格化后的对话文本
        """
        # 如果使用的是V2详细特质，将它们合并为V1格式以兼容现有流程
        if user_traits is None and (user_traits_chara or user_traits_address or user_traits_custom):
            user_traits = ""
            if user_traits_chara:
                user_traits += f"性格:{user_traits_chara}; "
            if user_traits_address:
                user_traits += f"称呼:{user_traits_address}; "
            if user_traits_custom:
                user_traits += f"自定义:{user_traits_custom}"
            user_traits = user_traits.strip("; ")
            
        if ai_traits is None and (ai_traits_chara or ai_traits_mantra or ai_traits_tone or (ai_emo_mode == "自定义模式" and ai_emo)):
            ai_traits = ""
            if ai_traits_chara:
                ai_traits += f"性格:{ai_traits_chara}; "
            if ai_traits_mantra:
                ai_traits += f"口头禅:{ai_traits_mantra}; "
            if ai_traits_tone:
                ai_traits += f"语气:{ai_traits_tone}; "
            if ai_emo_mode == "自定义模式" and ai_emo:
                ai_traits += f"表情/动作:{ai_emo}"
            elif ai_emo_mode == "自动模式":
                ai_traits += f"表情/动作:自动生成"
            ai_traits = ai_traits.strip("; ")
        
        return self.adapt_dialogue(dialogue_data, user_traits, ai_traits, language,
                                  user_traits_chara, user_traits_address, user_traits_custom,
                                  ai_traits_chara, ai_traits_mantra, ai_traits_tone, ai_emo, ai_emo_mode)
    
    def adapt_dialogue(self, dialogue_data, user_traits="", ai_traits="", language=None,
                      user_traits_chara="", user_traits_address="", user_traits_custom="",
                      ai_traits_chara="", ai_traits_mantra="", ai_traits_tone="", 
                      ai_emo="", ai_emo_mode="自动模式"):
        """基于特质改编对话风格"""
        # 输入验证
        if not isinstance(dialogue_data, dict):
            raise ValueError("dialogue_data 必须是字典类型")
        if not all(key in dialogue_data for key in ("original_text", "key_points", "intentions")):
            raise ValueError("dialogue_data 缺少必要字段")
            
        # 确保至少有一些特质信息（V1或V2格式）
        if not user_traits and not ai_traits and not user_traits_chara and not ai_traits_chara:
            raise ValueError("必须提供用户或AI的特质信息")
            
        try:
            prompt = self._build_adaptation_prompt(
                dialogue_data, user_traits, ai_traits, language,
                user_traits_chara, user_traits_address, user_traits_custom,
                ai_traits_chara, ai_traits_mantra, ai_traits_tone, ai_emo, ai_emo_mode
            )
            response = self.call_llm_api(prompt)
            
            # 验证响应长度
            if len(response) < 10:  # 简单有效性检查
                logging.warning(f"过短的响应内容: {response}")
                
            return response
            
        except Exception as e:
            logging.error(f"对话风格改编失败: {str(e)}")
            return dialogue_data.get("original_text", "")

    def _build_adaptation_prompt(self, dialogue_data, user_traits="", ai_traits="", language=None,
                               user_traits_chara="", user_traits_address="", user_traits_custom="",
                               ai_traits_chara="", ai_traits_mantra="", ai_traits_tone="", 
                               ai_emo="", ai_emo_mode="自动模式"):
        """构建用于风格改编的提示"""
        # 提取对话数据的关键元素
        original_text = dialogue_data.get("original_text", "")
        key_points = dialogue_data.get("key_points", [])
        intentions = dialogue_data.get("intentions", [])
        key_vocabulary = dialogue_data.get("key_vocabulary", [])
        key_sentences = dialogue_data.get("key_sentences", [])
        
        # 将列表转换为文本表示
        key_points_text = "\n".join([f"- {point}" for point in key_points])
        intentions_text = "\n".join([f"- {intent}" for intent in intentions])
        key_vocabulary_text = "\n".join([f"- {word}" for word in key_vocabulary])
        key_sentences_text = "\n".join([f"- {sentence}" for sentence in key_sentences])
        
        # 检测输出语言
        if not language:
            # 检测原始对话是否包含中文
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', original_text))
            if has_chinese:
                language = "中文"
            else:
                # 默认使用英文
                language = "英文"
        
        # 构建特质描述
        # 优先使用V2的详细特质，如果没有则使用V1的综合特质
        user_traits_description = ""
        ai_traits_description = ""
        
        if user_traits_chara or user_traits_address or user_traits_custom:
            if user_traits_chara:
                user_traits_description += f"性格特质: {user_traits_chara}\n"
            if user_traits_address:
                user_traits_description += f"他人称呼方式: {user_traits_address}\n"
            if user_traits_custom:
                user_traits_description += f"其他特质: {user_traits_custom}\n"
        elif user_traits:
            user_traits_description = f"用户角色特质: {user_traits}\n"
            
        if ai_traits_chara or ai_traits_mantra or ai_traits_tone or (ai_emo_mode == "自定义模式" and ai_emo):
            if ai_traits_chara:
                ai_traits_description += f"性格特质: {ai_traits_chara}\n"
            if ai_traits_mantra:
                ai_traits_description += f"口头禅: {ai_traits_mantra}\n"
            if ai_traits_tone:
                ai_traits_description += f"语气: {ai_traits_tone}\n"
            if ai_emo_mode == "自定义模式" and ai_emo:
                ai_traits_description += f"动作/表情描述: {ai_emo}\n"
            elif ai_emo_mode == "自动模式":
                ai_traits_description += f"动作/表情描述: 自动生成 (请根据AI性格和句子内容自动选择合适的动作和表情)\n"
        elif ai_traits:
            ai_traits_description = f"AI角色特质: {ai_traits}\n"
        
        # 根据语言构造提示
        if language == "英文":
            # 根据表情模式构建特定指令
            emotion_instructions = ""
            if ai_emo_mode == "自动模式":
                emotion_instructions = """
                5. IMPORTANT: For each line spoken by the AI character, automatically generate and include appropriate emotional expressions and physical actions based on the AI's personality and the content of the message
                """
            elif ai_emo_mode == "自定义模式" and ai_emo:
                emotion_instructions = f"""
                5. IMPORTANT: For each line spoken by the AI character, include emotional expressions and physical actions from this list: {ai_emo}
                """
            else:
                emotion_instructions = """
                5. Include appropriate emotional expressions and physical actions for the AI character when needed
                """
                
            prompt = f"""
            As a professional dialogue stylist AI, your task is to rewrite the original dialogue based on the given character traits while maintaining the same plot points and intentions of the original dialogue. Please keep the output in English.

            ## Original Dialogue Information
            Original dialogue text:
            {original_text}

            Key points:
            {key_points_text}

            Dialogue intentions:
            {intentions_text}

            Key vocabulary (must be preserved):
            {key_vocabulary_text}

            Key sentence structures (must be preserved):
            {key_sentences_text}

            ## Character Traits
            # User Character Details
            {user_traits_description}
            
            # AI Character Details
            {ai_traits_description}

            Please follow these requirements:
            1. Maintain all key points and intentions from the original dialogue
            2. Include ALL key vocabulary and sentence structures from the original dialogue
            3. Adjust the dialogue style, tone, and descriptions according to the character traits
            4. Keep the format of the dialogue with clear speaker distinctions
            {emotion_instructions}
            6. Keep the output in the SAME LANGUAGE as the original dialogue (English)
            7. Only return the rewritten dialogue text without additional explanations
            """
        else:
            # 根据表情模式构建特定指令
            emotion_instructions = ""
            if ai_emo_mode == "自动模式":
                emotion_instructions = """
                5. 重要提示：对于AI的每一句话，根据AI的性格特点和话语内容，自动生成并添加合适的情感表达和肢体动作描述
                """
            elif ai_emo_mode == "自定义模式" and ai_emo:
                emotion_instructions = f"""
                5. 重要提示：对于AI的每一句话，从以下列表中选择并添加情感表达和肢体动作描述：{ai_emo}
                """
            else:
                emotion_instructions = """
                5. 在需要时为AI角色添加适当的情感表达和肢体动作描述
                """
                
            prompt = f"""
            作为一个专业的对话风格改编 AI，你的任务是将原始对话根据给定的角色特质进行改编，同时保持原始对话的情节和意图不变。

            ## 原始对话信息
            对话原文：
            {original_text}

            关键节点：
            {key_points_text}

            对话意图：
            {intentions_text}

            关键词汇（必须保留）：
            {key_vocabulary_text}

            关键句型（必须保留）：
            {key_sentences_text}

            ## 角色特质
            # 用户角色详情
            {user_traits_description}
            
            # AI角色详情
            {ai_traits_description}

            请按照以下要求进行改编：
            1. 保持原始对话的全部关键节点和意图
            2. 包含原始对话中的所有关键词汇和句型
            3. 根据用户和 AI 的角色特质调整对话风格、语调和描述方式
            4. 请保持对话的格式，包括清晰的说话人区分
            {emotion_instructions}
            6. 重要提示：请保持输出语言与原始对话相同（中文）
            7. 请只返回改编后的对话文本，不需要额外的解释
            """
            
        return prompt
