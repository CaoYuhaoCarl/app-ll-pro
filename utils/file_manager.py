# -*- coding: utf-8 -*- # Ensure UTF-8 encoding for wider character support

import os
import json
import datetime
import uuid
import re

class FileManager:
    """
    文件管理类，负责对话内容的保存和读取
    支持各种格式的存储和读取
    """
    def __init__(self, base_dir=""):
        self.base_dir = base_dir
        
    def _ensure_directory(self, directory):
        """确保目录存在"""
        full_path = os.path.join(self.base_dir, directory)
        if not os.path.exists(full_path):
            os.makedirs(full_path)
        return full_path
    
    def _generate_filename(self, prefix, context):
        """生成文件名"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        safe_context = re.sub(r'[^\w\s-]', '', context)[:20].strip().replace(' ', '_')
        return f"{timestamp}_{safe_context}_{unique_id}"
    
    def save_initial_dialogue(self, dialogue_data, context, goal, directory="dialogue_data"):
        """
        保存 Agent 1 生成的结构化数据为 JSON 和 Markdown 格式
        
        Args:
            dialogue_data (dict): 对话数据
            context (str): 对话背景
            goal (str): 对话目标
            directory (str): 存储目录
            
        Returns:
            tuple: (json_path, md_path) 元组
        """
        try:
            # 创建存储目录（如果不存在）
            save_dir = self._ensure_directory(directory)
            
            # 生成文件名基础部分
            base_filename = self._generate_filename("dialogue", context)
            
            # JSON 文件路径
            json_filename = f"{save_dir}/{base_filename}.json"
            
            # Markdown 文件路径
            md_filename = f"{save_dir}/{base_filename}.md"
            
            # 添加元数据
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dialogue_data_with_meta = dialogue_data.copy()
            dialogue_data_with_meta["metadata"] = {
                "timestamp": timestamp,
                "context": context,
                "goal": goal
            }
            
            # 保存 JSON 文件
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(dialogue_data_with_meta, f, ensure_ascii=False, indent=2)
            
            # 生成并保存 Markdown 文件
            with open(md_filename, 'w', encoding='utf-8') as f:
                # 写入标题和元数据
                f.write(f"# 对话记录: {context[:30]}...\n\n")
                f.write(f"**生成时间**: {timestamp}\n\n")
                f.write(f"**对话背景**: {context}\n\n")
                f.write(f"**对话目标**: {goal}\n\n")
                
                # 写入原始对话内容
                f.write("## 对话内容\n\n")
                f.write("```\n")
                f.write(dialogue_data.get("original_text", ""))
                f.write("\n```\n\n")
                
                # 写入关键节点
                if dialogue_data.get("key_points"):
                    f.write("## 关键节点\n\n")
                    for point in dialogue_data.get("key_points", []):
                        f.write(f"- {point}\n")
                    f.write("\n")
                
                # 写入关键词汇
                if dialogue_data.get("key_vocabulary"):
                    f.write("## 关键情节词汇\n\n")
                    for vocab in dialogue_data.get("key_vocabulary", []):
                        f.write(f"- {vocab}\n")
                    f.write("\n")
                
                # 写入关键句型
                if dialogue_data.get("key_sentences"):
                    f.write("## 关键情节句型\n\n")
                    for sentence in dialogue_data.get("key_sentences", []):
                        f.write(f"- {sentence}\n")
                    f.write("\n")
                
                # 写入对话意图
                if dialogue_data.get("intentions"):
                    f.write("## 对话意图\n\n")
                    for intent in dialogue_data.get("intentions", []):
                        f.write(f"- {intent}\n")
            
            return (json_filename, md_filename)
        except Exception as e:
            print(f"保存对话数据时出错: {e}")
            return (None, None)
    
    def update_initial_dialogue(self, json_path, dialogue_data, context, goal):
        """
        更新已存在的对话数据文件（JSON 和 MD）
        
        Args:
            json_path (str): JSON 文件路径
            dialogue_data (dict): 新的对话数据
            context (str): 对话背景
            goal (str): 对话目标
            
        Returns:
            tuple: (json_path, md_path) 元组
        """
        try:
            if not json_path or not os.path.exists(json_path):
                return self.save_initial_dialogue(dialogue_data, context, goal)
                
            # 获取文件名基础部分和 MD 文件路径
            base_path = os.path.splitext(json_path)[0]
            md_path = f"{base_path}.md"
            
            # 从原始 JSON 文件读取元数据
            metadata = {}
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    original_data = json.load(f)
                    if "metadata" in original_data:
                        metadata = original_data["metadata"]
            except Exception:
                # 如果原始文件读取失败，使用新的元数据
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                metadata = {
                    "timestamp": timestamp,
                    "context": context,
                    "goal": goal
                }
            
            # 更新对话数据和元数据
            dialogue_data_with_meta = dialogue_data.copy()
            dialogue_data_with_meta["metadata"] = metadata
            
            # 保存更新后的 JSON 文件
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(dialogue_data_with_meta, f, ensure_ascii=False, indent=2)
            
            # 更新 Markdown 文件
            timestamp = metadata.get("timestamp", "")
            with open(md_path, 'w', encoding='utf-8') as f:
                # 写入标题和元数据
                f.write(f"# 对话记录: {context[:30]}...\n\n")
                f.write(f"**生成时间**: {timestamp}\n\n")
                f.write(f"**对话背景**: {metadata.get('context', context)}\n\n")
                f.write(f"**对话目标**: {metadata.get('goal', goal)}\n\n")
                
                # 写入原始对话内容
                f.write("## 对话内容\n\n")
                f.write("```\n")
                f.write(dialogue_data.get("original_text", ""))
                f.write("\n```\n\n")
                
                # 写入关键节点
                if dialogue_data.get("key_points"):
                    f.write("## 关键节点\n\n")
                    for point in dialogue_data.get("key_points", []):
                        f.write(f"- {point}\n")
                    f.write("\n")
                
                # 写入关键词汇
                if dialogue_data.get("key_vocabulary"):
                    f.write("## 关键情节词汇\n\n")
                    for vocab in dialogue_data.get("key_vocabulary", []):
                        f.write(f"- {vocab}\n")
                    f.write("\n")
                
                # 写入关键句型
                if dialogue_data.get("key_sentences"):
                    f.write("## 关键情节句型\n\n")
                    for sentence in dialogue_data.get("key_sentences", []):
                        f.write(f"- {sentence}\n")
                    f.write("\n")
                
                # 写入对话意图
                if dialogue_data.get("intentions"):
                    f.write("## 对话意图\n\n")
                    for intent in dialogue_data.get("intentions", []):
                        f.write(f"- {intent}\n")
            
            return (json_path, md_path)
        except Exception as e:
            print(f"更新对话数据文件时出错: {e}")
            return (None, None)
    
    # Function to prepare and format markdown output for AI traits
    def _format_ai_traits_for_markdown(self, ai_traits_data):
        """Helper function to format AI traits for markdown output based on emotion mode"""
        output = ""
        
        if ai_traits_data:
            if "ai_traits_chara" in ai_traits_data and ai_traits_data["ai_traits_chara"]:
                output += f"**性格特质**: {ai_traits_data['ai_traits_chara']}\n\n"
            if "ai_traits_mantra" in ai_traits_data and ai_traits_data["ai_traits_mantra"]:
                output += f"**口头禅**: {ai_traits_data['ai_traits_mantra']}\n\n"
            if "ai_traits_tone" in ai_traits_data and ai_traits_data["ai_traits_tone"]:
                output += f"**语气**: {ai_traits_data['ai_traits_tone']}\n\n"
                
            # Handle emotion display based on mode
            if "ai_emo_mode" in ai_traits_data:
                output += f"**动作/表情模式**: {ai_traits_data['ai_emo_mode']}\n\n"
                
                if ai_traits_data["ai_emo_mode"] == "自定义模式" and "ai_emo" in ai_traits_data and ai_traits_data["ai_emo"]:
                    output += f"**动作/表情描述**: {ai_traits_data['ai_emo']}\n\n"
                elif ai_traits_data["ai_emo_mode"] == "自动模式":
                    output += "**动作/表情描述**: 根据上下文自动生成\n\n"
            elif "ai_emo" in ai_traits_data and ai_traits_data["ai_emo"]:
                output += f"**动作/表情描述**: {ai_traits_data['ai_emo']}\n\n"
        
        return output
        
    def save_final_dialogue(self, dialogue_text, initial_dialogue_data, user_traits, ai_traits, 
                             user_traits_data=None, ai_traits_data=None, directory="final_dialogue_data"):
        """
        保存 Agent 2 生成的最终对话内容为 JSON 和 Markdown 格式
        
        Args:
            dialogue_text (str): 最终对话内容
            initial_dialogue_data (dict): 初始对话数据
            user_traits (str): 用户特征（V1格式）
            ai_traits (str): AI 特征（V1格式）
            user_traits_data (dict, optional): 用户特征详细数据（V2格式）
            ai_traits_data (dict, optional): AI特征详细数据（V2格式）
            directory (str): 存储目录
            
        Returns:
            tuple: (json_path, md_path) 元组
        """
        try:
            # 创建存储目录（如果不存在）
            save_dir = self._ensure_directory(directory)
            
            # 获取元数据
            metadata = {}
            context = ""
            goal = ""
            
            if initial_dialogue_data and "metadata" in initial_dialogue_data:
                metadata = initial_dialogue_data["metadata"]
                context = metadata.get("context", "")
                goal = metadata.get("goal", "")
            
            # 生成文件名基础部分
            base_filename = self._generate_filename("final", context)
            
            # JSON 文件路径
            json_filename = f"{save_dir}/{base_filename}.json"
            
            # Markdown 文件路径
            md_filename = f"{save_dir}/{base_filename}.md"
            
            # 添加元数据
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            final_dialogue_data = {
                "final_text": dialogue_text,
                "user_traits": user_traits,
                "ai_traits": ai_traits,
                "original_dialogue": initial_dialogue_data,
                "metadata": {
                    "timestamp": timestamp,
                    "context": context,
                    "goal": goal
                }
            }
            
            # 添加V2格式的详细特质数据（如果有）
            if user_traits_data:
                final_dialogue_data["user_traits_data"] = user_traits_data
            if ai_traits_data:
                final_dialogue_data["ai_traits_data"] = ai_traits_data
            
            # 保存 JSON 文件
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(final_dialogue_data, f, ensure_ascii=False, indent=2)
            
            # 生成并保存 Markdown 文件
            with open(md_filename, 'w', encoding='utf-8') as f:
                # 写入标题和元数据
                f.write(f"# 最终对话: {context[:30]}...\n\n")
                f.write(f"**生成时间**: {timestamp}\n\n")
                f.write(f"**对话背景**: {context}\n\n")
                f.write(f"**对话目标**: {goal}\n\n")
                
                # 写入角色特质
                f.write("## 角色特质\n\n")
                
                # 优先使用V2格式的详细特质
                if user_traits_data:
                    f.write("### 用户角色详情\n\n")
                    if user_traits_data.get("user_traits_chara"):
                        f.write(f"**性格特质**: {user_traits_data['user_traits_chara']}\n\n")
                    if user_traits_data.get("user_traits_address"):
                        f.write(f"**称呼方式**: {user_traits_data['user_traits_address']}\n\n")
                    if user_traits_data.get("user_traits_custom"):
                        f.write(f"**自定义特质**: {user_traits_data['user_traits_custom']}\n\n")
                else:
                    # 使用V1的综合特质
                    f.write(f"**用户特征**: {user_traits}\n\n")
                
                if ai_traits_data:
                    f.write("### AI角色详情\n\n")
                    f.write(self._format_ai_traits_for_markdown(ai_traits_data))
                else:
                    # 使用V1的综合特质
                    f.write(f"**AI 特征**: {ai_traits}\n\n")
                
                # 写入最终对话内容
                f.write("## 最终对话\n\n")
                f.write("```\n")
                f.write(dialogue_text)
                f.write("\n```\n")
            
            return (json_filename, md_filename)
        except Exception as e:
            print(f"保存最终对话内容时出错: {e}")
            return (None, None)
    
    def update_final_dialogue(self, json_path, dialogue_text, initial_dialogue_data, user_traits, ai_traits,
                              user_traits_data=None, ai_traits_data=None):
        """
        更新已存在的最终对话内容文件（JSON 和 MD）
        
        Args:
            json_path (str): JSON 文件路径
            dialogue_text (str): 新的最终对话内容
            initial_dialogue_data (dict): 初始对话数据
            user_traits (str): 用户特征（V1格式）
            ai_traits (str): AI 特征（V1格式）
            user_traits_data (dict, optional): 用户特征详细数据（V2格式）
            ai_traits_data (dict, optional): AI特征详细数据（V2格式）
            
        Returns:
            tuple: (json_path, md_path) 元组
        """
        try:
            if not json_path or not os.path.exists(json_path):
                # 如果文件不存在，创建新文件
                context = ""
                goal = ""
                if initial_dialogue_data and "metadata" in initial_dialogue_data:
                    metadata = initial_dialogue_data["metadata"]
                    context = metadata.get("context", "")
                    goal = metadata.get("goal", "")
                return self.save_final_dialogue(dialogue_text, initial_dialogue_data, user_traits, ai_traits, 
                                              user_traits_data, ai_traits_data)
            
            # 获取文件名基础部分和 MD 文件路径
            base_path = os.path.splitext(json_path)[0]
            md_path = f"{base_path}.md"
            
            # 从原始 JSON 文件读取元数据
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    original_data = json.load(f)
                    metadata = original_data.get("metadata", {})
                    original_initial_dialogue = original_data.get("original_dialogue", {})
            except Exception:
                # 如果原始文件读取失败，使用新的元数据
                metadata = {}
                if initial_dialogue_data and "metadata" in initial_dialogue_data:
                    metadata = initial_dialogue_data["metadata"]
                original_initial_dialogue = initial_dialogue_data
            
            # 如果没有初始对话数据，使用原始数据
            if not initial_dialogue_data:
                initial_dialogue_data = original_initial_dialogue
            
            # 获取对话背景和目标
            context = metadata.get("context", "")
            goal = metadata.get("goal", "")
            
            # 更新时间戳
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            metadata["timestamp"] = timestamp
            
            # 构造新的最终对话数据
            final_dialogue_data = {
                "final_text": dialogue_text,
                "user_traits": user_traits,
                "ai_traits": ai_traits,
                "original_dialogue": initial_dialogue_data,
                "metadata": metadata
            }
            
            # 添加V2格式的详细特质数据（如果有）
            if user_traits_data:
                final_dialogue_data["user_traits_data"] = user_traits_data
            if ai_traits_data:
                final_dialogue_data["ai_traits_data"] = ai_traits_data
            
            # 保存更新后的 JSON 文件
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(final_dialogue_data, f, ensure_ascii=False, indent=2)
            
            # 更新 Markdown 文件
            with open(md_path, 'w', encoding='utf-8') as f:
                # 写入标题和元数据
                f.write(f"# 最终对话: {context[:30]}...\n\n")
                f.write(f"**生成时间**: {timestamp}\n\n")
                f.write(f"**对话背景**: {context}\n\n")
                f.write(f"**对话目标**: {goal}\n\n")
                
                # 写入角色特质
                f.write("## 角色特质\n\n")
                
                # 优先使用V2格式的详细特质
                if user_traits_data:
                    f.write("### 用户角色详情\n\n")
                    if user_traits_data.get("user_traits_chara"):
                        f.write(f"**性格特质**: {user_traits_data['user_traits_chara']}\n\n")
                    if user_traits_data.get("user_traits_address"):
                        f.write(f"**称呼方式**: {user_traits_data['user_traits_address']}\n\n")
                    if user_traits_data.get("user_traits_custom"):
                        f.write(f"**自定义特质**: {user_traits_data['user_traits_custom']}\n\n")
                else:
                    # 使用V1的综合特质
                    f.write(f"**用户特征**: {user_traits}\n\n")
                
                if ai_traits_data:
                    f.write("### AI角色详情\n\n")
                    f.write(self._format_ai_traits_for_markdown(ai_traits_data))
                else:
                    # 使用V1的综合特质
                    f.write(f"**AI 特征**: {ai_traits}\n\n")
                
                # 写入最终对话内容
                f.write("## 最终对话\n\n")
                f.write("```\n")
                f.write(dialogue_text)
                f.write("\n```\n")
            
            return (json_path, md_path)
        except Exception as e:
            print(f"更新最终对话内容文件时出错: {e}")
            return (None, None)
