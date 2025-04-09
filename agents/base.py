# -*- coding: utf-8 -*- # Ensure UTF-8 encoding for wider character support

from openai import OpenAI
import json
import requests
import logging
import time
import random

class DialogueAgent:
    """
    对话生成代理的基类，提供通用方法和属性
    所有特定的Agent应继承此类并实现自己的方法
    """
    def __init__(self, client, model="o3-mini", api_type="openai"):
        self.model = model
        self.client = client
        self.api_type = api_type  # "openai" or "openrouter"
        self.agent_type = "base"  # 用于标识Agent类型
        self.description = "基础对话代理"  # 简要描述
        self.max_retries = 3  # 最大重试次数
        
    def get_agent_info(self):
        """获取Agent的基本信息"""
        return {
            "type": self.agent_type,
            "description": self.description,
            "model": self.model,
            "api_type": self.api_type
        }
    
    def call_llm_api(self, prompt, tools=None):
        """使用 LLM API 调用模型，支持 OpenAI 和 OpenRouter"""
        try:
            if self.api_type == "openai":
                return self._call_openai_api(prompt, tools)
            elif self.api_type == "openrouter":
                return self._call_openrouter_api_with_retry(prompt, tools)
            else:
                error_msg = f"不支持的 API 类型: {self.api_type}"
                logging.error(error_msg)
                return None
        except Exception as e:
            error_msg = f"API 调用错误: {e}"
            logging.error(error_msg)
            return None
    
    def _call_openai_api(self, prompt, tools=None):
        """调用 OpenAI API"""
        try:
            if tools:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    tools=tools
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                
            # 从响应中提取内容
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content
            else:
                logging.error("OpenAI API 未返回有效内容")
                return None
        except Exception as e:
            logging.error(f"OpenAI API 调用错误: {e}")
            return None
    
    def _call_openrouter_api_with_retry(self, prompt, tools=None):
        """使用重试机制调用 OpenRouter API"""
        retries = 0
        backoff_time = 1  # 初始退避时间(秒)
        
        while retries < self.max_retries:
            result = self._call_openrouter_api(prompt, tools)
            # 如果成功获取结果或者不是因为速率限制导致的错误，直接返回
            if isinstance(result, dict) and "error_type" in result:
                if result["error_type"] == "rate_limit":
                    # 是速率限制错误，需要重试
                    reset_time = result.get("reset_time", 0)
                    wait_time = max(backoff_time, min(60, reset_time))  # 最多等待60秒
                    logging.warning(f"OpenRouter API 速率限制，等待 {wait_time} 秒后重试 (尝试 {retries+1}/{self.max_retries})")
                    time.sleep(wait_time)
                    # 指数退避
                    backoff_time = backoff_time * 2 + random.uniform(0, 1)
                    retries += 1
                else:
                    # 其他类型的错误，直接返回错误信息
                    return result.get("message", "OpenRouter API 调用失败")
            else:
                # 正常结果或其他非速率限制错误
                return result
        
        # 达到最大重试次数后仍失败
        return "OpenRouter API 调用失败: 达到速率限制，请稍后再试或考虑升级账户计划"
    
    def _call_openrouter_api(self, prompt, tools=None):
        """调用 OpenRouter API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.client.get('api_key')}"
        }
        
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        # 添加工具调用支持，如果相关模型支持
        if tools:
            data["tools"] = tools
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30  # 添加超时设置
            )
            
            if response.status_code == 200:
                result = response.json()
                try:
                    # 正确处理OpenRouter的响应结构
                    if "choices" in result and len(result["choices"]) > 0:
                        return result["choices"][0]["message"]["content"]
                    else:
                        logging.error(f"OpenRouter API 响应异常: {result}")
                        return {"error_type": "response_format", "message": "API 响应格式异常"}
                except Exception as e:
                    error_msg = f"OpenRouter API 响应解析错误: {e}, 响应内容: {result}"
                    logging.error(error_msg)
                    return {"error_type": "parse_error", "message": error_msg}
            elif response.status_code == 429:
                # 处理速率限制错误
                error_data = response.json()
                logging.error(f"OpenRouter API 响应异常: {error_data}")
                
                # 尝试提取速率限制重置时间
                reset_time = 0
                try:
                    if "error" in error_data and "metadata" in error_data["error"] and "headers" in error_data["error"]["metadata"]:
                        headers = error_data["error"]["metadata"]["headers"]
                        if "X-RateLimit-Reset" in headers:
                            reset_timestamp = int(headers["X-RateLimit-Reset"]) / 1000  # 转换为秒
                            reset_time = max(0, reset_timestamp - time.time())
                except Exception as e:
                    logging.warning(f"提取速率限制重置时间失败: {e}")
                
                error_message = "速率限制超出"
                if "error" in error_data and "message" in error_data["error"]:
                    error_message = error_data["error"]["message"]
                
                return {
                    "error_type": "rate_limit", 
                    "message": f"OpenRouter API {error_message}",
                    "reset_time": reset_time
                }
            else:
                error_msg = f"OpenRouter API 错误 ({response.status_code}): {response.text}"
                logging.error(error_msg)
                return {"error_type": "api_error", "message": error_msg}
        except requests.exceptions.Timeout:
            error_msg = "OpenRouter API 请求超时"
            logging.error(error_msg)
            return {"error_type": "timeout", "message": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"OpenRouter API 请求异常: {e}"
            logging.error(error_msg)
            return {"error_type": "request_error", "message": error_msg}
        except Exception as e:
            error_msg = f"OpenRouter API 未知错误: {e}"
            logging.error(error_msg)
            return {"error_type": "unknown", "message": error_msg}
    
    def process(self, *args, **kwargs):
        """处理输入并生成输出的抽象方法，子类必须实现此方法"""
        raise NotImplementedError("子类必须实现process方法")
