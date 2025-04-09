# -*- coding: utf-8 -*- # Ensure UTF-8 encoding for wider character support

from typing import Dict, Type, List, Optional, Union, Any
from .base import DialogueAgent
from .dialogue_agents import InitialDialogueAgent, StyleAdaptationAgent

class AgentRegistry:
    """
    Agent注册表，管理所有可用的Agent
    提供注册、获取和列出Agent的功能
    """
    def __init__(self):
        self._agents: Dict[str, Type[DialogueAgent]] = {}
        self._initialized = False
        
    def register(self, agent_type: str, agent_class: Type[DialogueAgent]) -> None:
        """
        注册一个Agent类
        
        Args:
            agent_type: Agent类型标识符
            agent_class: DialogueAgent子类
        """
        self._agents[agent_type] = agent_class
        
    def get_agent_class(self, agent_type: str) -> Optional[Type[DialogueAgent]]:
        """
        获取指定类型的Agent类
        
        Args:
            agent_type: Agent类型标识符
            
        Returns:
            DialogueAgent子类或None（如果不存在）
        """
        return self._agents.get(agent_type)
    
    def create_agent(self, agent_type: str, client: Union[Any, Dict[str, str]], model="o3-mini", api_type="openai") -> Optional[DialogueAgent]:
        """
        创建指定类型的Agent实例
        
        Args:
            agent_type: Agent类型标识符
            client: OpenAI客户端实例或OpenRouter配置字典
            model: 使用的模型名称
            api_type: API类型 ("openai" 或 "openrouter")
            
        Returns:
            DialogueAgent实例或None（如果类型不存在）
        """
        agent_class = self.get_agent_class(agent_type)
        if agent_class:
            return agent_class(client, model, api_type)
        return None
    
    def list_available_agents(self) -> List[str]:
        """
        列出所有可用的Agent类型
        
        Returns:
            Agent类型标识符列表
        """
        return list(self._agents.keys())
    
    def initialize_default_agents(self) -> None:
        """
        初始化默认的Agent
        """
        if not self._initialized:
            self.register("initial_dialogue", InitialDialogueAgent)
            self.register("style_adaptation", StyleAdaptationAgent)
            self._initialized = True

# 创建全局的Agent注册表实例
agent_registry = AgentRegistry()
agent_registry.initialize_default_agents()
