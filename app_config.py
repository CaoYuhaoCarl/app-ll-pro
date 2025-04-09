# -*- coding: utf-8 -*- # Ensure UTF-8 encoding for wider character support

import os
import streamlit as st
import logging
import time
import requests
import json
import re
import random
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

class AppConfig:
    """
    应用程序配置类，管理应用设置和状态
    """
    # 默认设置
    DEFAULT_SETTINGS = {
        "api_provider": "openai",  # 'openai' 或 'openrouter'
        "model": "o3-mini",
        "work_mode": "人机协作",
        "language_options": ["英文", "中文", "日文", "韩文", "法文", "德文", "西班牙文"],
        "difficulty_options": ["A1", "A2", "B1", "B2", "C1", "C2"],
        "dialogue_mode_options": ["AI先说", "用户先说"],
        "default_num_turns": 6,
        "default_difficulty": "B1",
        # 添加默认输入值
        "context": "在一家温馨热闹的咖啡店里，A正站起身去取咖啡时，不小心与B发生了轻微碰撞......",
        "goal": "交换了联系方式，并成功加入了到了读书俱乐部",
        # V1 版本的用户特质和AI特质
        "user_traits": "男，内向",
        "ai_traits": "女，活泼，善交流，口头禅\"my god\", 加入\"动作表情描述语\"",
        # V2 版本的拆分特质字段
        "user_traits_chara": "内向，谨慎，喜欢文学",
        "user_traits_address": "Honey",
        "user_traits_custom": "高冷寡言",
        "ai_traits_chara": "活泼开朗，善于表达",
        "ai_traits_mantra": "wow, my god, what",
        "ai_traits_tone": "热情，亲切",
        "ai_emo": "微笑着, 惊讶地睁大眼睛, 轻轻点头",
        "ai_emo_mode": "自动模式",  # "自动模式" 或 "自定义模式"
        "ai_emo_mode_options": ["自动模式", "自定义模式"],
        # 其他设置
        "language": "英文",
        # 新增自定义单词和句型
        "custom_vocabulary": "",
        "custom_sentence": "",
        # OpenRouter 配置
        "openrouter_api_key": "",
        "openrouter_models_cache": [],
        "openrouter_full_models_data": [],  # 存储完整的模型数据
        "openrouter_cache_timestamp": 0,
        "openrouter_model_search_query": "",  # 存储模型搜索关键词
    }
    
    def __init__(self):
        # 尝试从环境变量中加载 API 密钥
        try:
            load_dotenv()
            logging.info("环境变量文件(.env)加载成功")
            
            # 加载 OpenAI API 密钥
            openai_key = os.getenv("OPENAI_API_KEY", "")
            if openai_key:
                logging.info("成功加载 OpenAI API 密钥")
                os.environ["OPENAI_API_KEY"] = openai_key
            else:
                logging.warning("未找到 OpenAI API 密钥")
            
            # 加载 OpenRouter API 密钥
            openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
            if openrouter_key:
                logging.info("成功加载 OpenRouter API 密钥")
                self.DEFAULT_SETTINGS["openrouter_api_key"] = openrouter_key
            else:
                logging.warning("未找到 OpenRouter API 密钥")
        except Exception as e:
            logging.error(f"加载环境变量文件(.env)失败: {e}")
            
        self.initialize_session_state()
    
    def initialize_session_state(self) -> None:
        """初始化会话状态变量"""
        # 检查并初始化会话状态变量
        if 'dialogue_data' not in st.session_state:
            st.session_state.dialogue_data = None
            
        if 'dialogue_edited' not in st.session_state:
            st.session_state.dialogue_edited = False
            
        if 'saved_path' not in st.session_state:
            st.session_state.saved_path = None
            
        if 'final_dialogue' not in st.session_state:
            st.session_state.final_dialogue = None
            
        if 'final_dialogue_edited' not in st.session_state:
            st.session_state.final_dialogue_edited = False
            
        if 'final_saved_path' not in st.session_state:
            st.session_state.final_saved_path = None
            
        # 初始化设置变量
        if 'settings' not in st.session_state:
            st.session_state.settings = self.DEFAULT_SETTINGS.copy()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取设置项值"""
        return st.session_state.settings.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """设置设置项值"""
        st.session_state.settings[key] = value
    
    def reset_session(self) -> None:
        """重置会话状态"""
        st.session_state.dialogue_data = None
        st.session_state.dialogue_edited = False
        st.session_state.saved_path = None
        st.session_state.final_dialogue = None
        st.session_state.final_dialogue_edited = False
        st.session_state.final_saved_path = None
        
    def get_available_models(self) -> List[str]:
        """根据当前API提供商获取可用模型列表"""
        api_provider = self.get_setting("api_provider")
        
        if api_provider == "openai":
            return ["o3-mini", "gpt-4o-mini", "gpt-4o"]
        elif api_provider == "openrouter":
            # 获取 OpenRouter 可用模型
            return self.get_openrouter_models()
        else:
            return ["o3-mini"]  # 默认模型
    
    def get_work_modes(self) -> List[str]:
        """获取可用工作模式列表"""
        return ["人机协作", "自动模式"]
    
    def get_api_providers(self) -> List[str]:
        """获取可用的API提供商列表"""
        return ["openai", "openrouter"]
    
    def get_openrouter_models(self) -> List[str]:
        """获取OpenRouter可用模型列表，应用搜索过滤"""
        # 获取完整模型数据
        self._update_openrouter_models_if_needed()
        
        # 获取当前的搜索查询
        search_query = self.get_setting("openrouter_model_search_query", "").strip().lower()
        
        # 从完整数据中提取ID列表，根据搜索查询进行过滤
        if search_query:
            filtered_models = self._filter_models_by_search(search_query)
            if filtered_models:
                return filtered_models
            else:
                return ["未找到匹配的模型"]
        else:
            # 无搜索查询时返回所有模型ID
            return self.get_setting("openrouter_models_cache", ["请设置OpenRouter API密钥"])
    
    def _update_openrouter_models_if_needed(self) -> None:
        """如果需要，更新OpenRouter模型数据"""
        # 检查缓存是否过期(缓存1小时)
        cached_models = self.get_setting("openrouter_models_cache", [])
        cache_timestamp = self.get_setting("openrouter_cache_timestamp", 0)
        
        if cached_models and (time.time() - cache_timestamp < 3600):
            return
        
        # 缓存过期或为空，需要重新获取
        api_key = self.get_setting("openrouter_api_key", "")
        if not api_key:
            self.set_setting("openrouter_models_cache", ["请设置OpenRouter API密钥"])
            self.set_setting("openrouter_full_models_data", [])
            return
            
        try:
            # 添加重试机制
            max_retries = 3
            retry_count = 0
            retry_delay = 1  # 初始等待时间(秒)
            
            while retry_count < max_retries:
                headers = {
                    "Authorization": f"Bearer {api_key}"
                }
                response = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=headers,
                    timeout=10  # 添加超时设置
                )
                
                if response.status_code == 200:
                    models_data = response.json()
                    
                    # 存储完整模型数据
                    full_models_data = models_data.get("data", [])
                    self.set_setting("openrouter_full_models_data", full_models_data)
                    
                    # 提取模型ID列表
                    models = [model["id"] for model in full_models_data]
                    self.set_setting("openrouter_models_cache", models)
                    self.set_setting("openrouter_cache_timestamp", time.time())
                    return
                elif response.status_code == 429:
                    # 处理速率限制
                    error_data = response.json()
                    logging.error(f"获取OpenRouter模型列表时遇到速率限制: {error_data}")
                    
                    # 尝试提取重置时间
                    reset_time = 0
                    try:
                        if "error" in error_data and "metadata" in error_data["error"] and "headers" in error_data["error"]["metadata"]:
                            headers = error_data["error"]["metadata"]["headers"]
                            if "X-RateLimit-Reset" in headers:
                                reset_timestamp = int(headers["X-RateLimit-Reset"]) / 1000  # 转换为秒
                                reset_time = max(0, reset_timestamp - time.time())
                    except Exception as e:
                        logging.warning(f"提取速率限制重置时间失败: {e}")
                    
                    # 计算等待时间
                    wait_time = max(retry_delay, min(60, reset_time))  # 最多等待60秒
                    logging.warning(f"OpenRouter API 速率限制，等待 {wait_time} 秒后重试 (尝试 {retry_count+1}/{max_retries})")
                    time.sleep(wait_time)
                    
                    # 指数退避
                    retry_delay = retry_delay * 2 + random.uniform(0, 1)
                    retry_count += 1
                else:
                    # 其他错误，直接退出重试
                    logging.error(f"获取OpenRouter模型列表失败: {response.status_code} - {response.text}")
                    self.set_setting("openrouter_models_cache", ["获取模型列表失败"])
                    self.set_setting("openrouter_full_models_data", [])
                    return
            
            # 达到最大重试次数
            self.set_setting("openrouter_models_cache", ["API速率限制，请稍后再试"])
            self.set_setting("openrouter_full_models_data", [])
            
        except requests.exceptions.Timeout:
            logging.error("获取OpenRouter模型列表超时")
            self.set_setting("openrouter_models_cache", ["API请求超时"])
            self.set_setting("openrouter_full_models_data", [])
        except requests.exceptions.RequestException as e:
            logging.error(f"获取OpenRouter模型列表请求异常: {e}")
            self.set_setting("openrouter_models_cache", ["API连接错误"])
            self.set_setting("openrouter_full_models_data", [])
        except Exception as e:
            logging.error(f"获取OpenRouter模型列表出错: {str(e)}")
            self.set_setting("openrouter_models_cache", ["API连接错误"])
            self.set_setting("openrouter_full_models_data", [])
    
    def _filter_models_by_search(self, search_query: str) -> List[str]:
        """根据搜索关键词过滤模型列表"""
        full_models_data = self.get_setting("openrouter_full_models_data", [])
        if not full_models_data:
            return []
            
        # 将搜索查询按空格分割为多个关键词
        keywords = search_query.lower().split()
        
        filtered_models = []
        for model in full_models_data:
            model_id = model.get("id", "").lower()
            model_name = model.get("name", "").lower()
            model_description = model.get("description", "").lower()
            context_length = str(model.get("context_length", "")).lower()
            
            # 组合所有可搜索的文本
            searchable_text = f"{model_id} {model_name} {model_description} {context_length}"
            
            # 如果所有关键词都在可搜索文本中，则添加此模型
            if all(keyword in searchable_text for keyword in keywords):
                filtered_models.append(model["id"])
                
        return filtered_models
    
    def get_model_details_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        """根据模型ID获取详细信息"""
        full_models_data = self.get_setting("openrouter_full_models_data", [])
        for model in full_models_data:
            if model.get("id") == model_id:
                return model
        return None
            
    def create_api_client(self):
        """根据当前设置创建合适的API客户端"""
        api_provider = self.get_setting("api_provider")
        
        if api_provider == "openai":
            try:
                from openai import OpenAI
                client = OpenAI()
                return client
            except Exception as e:
                logging.error(f"创建OpenAI客户端失败: {str(e)}")
                return None
        elif api_provider == "openrouter":
            # 对于OpenRouter，返回一个配置字典
            return {
                "api_key": self.get_setting("openrouter_api_key", ""),
                "api_base": "https://openrouter.ai/api/v1"
            }
        
        return None
