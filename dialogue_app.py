# -*- coding: utf-8 -*- # Ensure UTF-8 encoding for wider character support

import streamlit as st
# Set page config as the very first Streamlit command
st.set_page_config(layout="wide", page_title="AI Dialogue Personalizer")

from openai import OpenAI, OpenAIError
import os
import logging
import requests
from dotenv import load_dotenv

# 导入重构后的组件
from agents.registry import agent_registry
from utils.file_manager import FileManager
from app_config import AppConfig

# 配置日志
logging.basicConfig(level=logging.INFO)

# --- 加载环境变量 ---
try:
    load_dotenv()
    logging.info("Attempted to load .env file.")
except Exception as e:
    logging.error(f"Error loading .env file (this might be ignorable if not using .env): {e}")

# --- 配置 ---
# 尝试初始化OpenAI client
API_KEY_VALID = False # 默认无效
API_ERROR_MESSAGE = None # 存储具体错误信息

# 初始化应用配置
app_config = AppConfig()
# 初始化文件管理器
file_manager = FileManager()

def show_api_error(error_message, suggestion=None):
    """显示API错误信息"""
    with st.error(error_message):
        if suggestion:
            st.write(suggestion)
        if "rate_limit" in error_message.lower() or "rate limit" in error_message.lower():
            st.write("**OpenRouter免费账户有使用限制：**")
            st.write("1. 每天模型调用次数限制")
            st.write("2. 每分钟请求次数限制")
            st.write("\n**解决方案：**")
            st.write("- 等待一段时间后再试")
            st.write("- 考虑升级到付费账户")
            st.write("- 尝试使用OpenAI API")

# --- Streamlit UI 实现 ---

def render_sidebar():
    """渲染侧边栏内容"""
    with st.sidebar:
        st.header("模型设置")
        
        # API提供商选择
        api_provider = st.selectbox(
            "选择API提供商",
            app_config.get_api_providers(),
            index=app_config.get_api_providers().index(app_config.get_setting("api_provider"))
        )
        app_config.set_setting("api_provider", api_provider)
        
        # 根据API提供商显示相应设置
        if api_provider == "openai":
            openai_api_key = st.text_input(
                "OpenAI API密钥 (可选，默认使用环境变量)",
                value="",
                type="password",
                help="如果已在环境变量中设置，可留空"
            )
            if openai_api_key:
                os.environ["OPENAI_API_KEY"] = openai_api_key
                
            # 测试API连接
            if st.button("测试API连接"):
                with st.spinner("正在测试API连接..."):
                    try:
                        client = OpenAI()
                        client.models.list()
                        st.success("OpenAI API连接成功!")
                    except Exception as e:
                        st.error(f"API连接失败: {str(e)}")
        
        elif api_provider == "openrouter":
            openrouter_api_key = st.text_input(
                "OpenRouter API密钥",
                value=app_config.get_setting("openrouter_api_key", ""),
                type="password"
            )
            app_config.set_setting("openrouter_api_key", openrouter_api_key)
            
            # OpenRouter使用提示
            with st.expander("OpenRouter使用提示", expanded=False):
                st.write("**免费账户限制**")
                st.write("- 每天有模型调用次数限制")
                st.write("- 每分钟有请求次数限制")
                st.write("- 超出限制会返回429错误")
                st.write("")
                st.write("**最佳实践**")
                st.write("- 减少不必要的API调用")
                st.write("- 遇到速率限制时等待几分钟再试")
                st.write("- 考虑升级到付费账户获取更高限额")
                st.write("- 如需频繁调用，建议使用OpenAI API")
            
            # 测试API连接并刷新模型列表
            if st.button("测试API连接并刷新模型列表"):
                with st.spinner("正在测试API连接..."):
                    if not openrouter_api_key:
                        st.error("请输入OpenRouter API密钥")
                    else:
                        try:
                            headers = {
                                "Authorization": f"Bearer {openrouter_api_key}"
                            }
                            response = requests.get(
                                "https://openrouter.ai/api/v1/models",
                                headers=headers,
                                timeout=10
                            )
                            
                            if response.status_code == 200:
                                models_data = response.json()
                                # 存储完整模型数据
                                full_models_data = models_data.get("data", [])
                                app_config.set_setting("openrouter_full_models_data", full_models_data)
                                
                                # 提取模型ID列表
                                models = [model["id"] for model in full_models_data]
                                app_config.set_setting("openrouter_models_cache", models)
                                app_config.set_setting("openrouter_cache_timestamp", 0)  # 强制刷新
                                st.success(f"连接成功! 获取到{len(models)}个可用模型")
                            elif response.status_code == 429:
                                error_data = response.json()
                                error_message = "速率限制超出"
                                if "error" in error_data and "message" in error_data["error"]:
                                    error_message = error_data["error"]["message"]
                                    
                                st.error(f"API连接失败: 速率限制错误 - {error_message}")
                                with st.error("速率限制提示"):
                                    st.write("您已超出OpenRouter免费账户的API使用限制。")
                                    st.write("请等待一段时间后再试，或考虑升级到付费账户。")
                            else:
                                st.error(f"API连接失败: {response.status_code} - {response.text}")
                        except Exception as e:
                            st.error(f"API连接失败: {str(e)}")
            
            # 如果是OpenRouter，添加模型搜索框
            st.subheader("模型搜索")
            current_search = app_config.get_setting("openrouter_model_search_query", "")
            search_query = st.text_input(
                "输入关键词搜索模型",
                value=current_search,
                placeholder="例如: gpt claude llama 32k",
                help="可搜索模型ID、名称和描述，支持多关键词(空格分隔)"
            )
            
            # 更新搜索查询
            if search_query != current_search:
                app_config.set_setting("openrouter_model_search_query", search_query)
            
            # 清除搜索按钮
            if search_query and st.button("清除搜索"):
                app_config.set_setting("openrouter_model_search_query", "")
                search_query = ""
        
        # 模型选择
        available_models = app_config.get_available_models()
        
        # 对于OpenRouter，优化模型选择体验
        if api_provider == "openrouter" and available_models and available_models[0] not in ["请设置OpenRouter API密钥", "API连接错误", "获取模型列表失败", "未找到匹配的模型", "API速率限制，请稍后再试", "API请求超时"]:
            # 获取当前选择的模型
            current_model = app_config.get_setting("model")
            
            # 如果当前模型不在可用列表中，选择一个默认的
            if current_model not in available_models:
                current_model = available_models[0]
            
            # 创建一个格式化的下拉选择框
            model_options = []
            for model_id in available_models:
                # 获取模型详情
                model_details = app_config.get_model_details_by_id(model_id)
                if model_details:
                    model_name = model_details.get("name", model_id)
                    context_length = model_details.get("context_length", "未知")
                    display_name = f"{model_name} ({context_length}k)"
                else:
                    display_name = model_id
                model_options.append({"id": model_id, "display": display_name})
            
            # 创建用于显示的选项列表和对应的ID映射
            display_options = [m["display"] for m in model_options]
            id_to_index = {m["id"]: i for i, m in enumerate(model_options)}
            
            # 选择框
            selected_index = id_to_index.get(current_model, 0)
            selected_display = st.selectbox(
                "选择 LLM 模型",
                options=display_options,
                index=min(selected_index, len(display_options)-1)
            )
            
            # 从显示名称映射回模型ID
            selected_model = model_options[display_options.index(selected_display)]["id"]
            
            # 显示选定模型的详细信息
            model_details = app_config.get_model_details_by_id(selected_model)
            if model_details:
                with st.expander("模型详情", expanded=False):
                    st.write(f"**名称**: {model_details.get('name', '未知')}")
                    st.write(f"**上下文长度**: {model_details.get('context_length', '未知')}k")
                    if model_details.get('description'):
                        st.write(f"**描述**: {model_details.get('description')}")
            
            app_config.set_setting("model", selected_model)
        elif api_provider == "openrouter" and available_models and available_models[0] in ["API速率限制，请稍后再试", "API请求超时"]:
            # 显示警告信息
            st.warning("获取模型列表失败：速率限制或超时")
            st.info("请稍后再试，或切换到OpenAI API使用")
            
            # 使用缓存的模型或默认值
            model = st.selectbox(
                "选择 LLM 模型",
                ["anthropic/claude-3-opus-20240229", "anthropic/claude-3-sonnet-20240229", "openai/gpt-4-turbo", "meta-llama/llama-3-70b-instruct"] 
            )
            app_config.set_setting("model", model)
        else:
            # 普通模型选择（OpenAI或错误状态）
            model = st.selectbox(
                "选择 LLM 模型",
                available_models
            )
            app_config.set_setting("model", model)
        
        # 增加模式选择
        st.header("创作模式")
        work_mode = st.radio(
            "选择创作模式",
            app_config.get_work_modes(),
            help="自动模式：Agent1生成内容自动传给Agent2；人机协作：Agent1生成后，人工编辑再传给Agent2"
        )
        app_config.set_setting("work_mode", work_mode)

def render_agent1_inputs(col):
    """渲染Agent 1的输入界面"""
    with col:
        st.header("Agent 1: 初始对话生成")
        
        # 使用默认值
        default_context = app_config.get_setting("context", "")
        context = st.text_area(
            "对话背景",
            value=default_context,
            placeholder="例如：咖啡馆邂逅、办公室会议等",
            height=100,
            key="context_input"
        )
        
        dialogue_mode = st.radio(
            "对话模式",
            options=app_config.get_setting("dialogue_mode_options"),
            key="dialogue_mode_input"
        )
        
        # 使用默认值
        default_goal = app_config.get_setting("goal", "")
        goal = st.text_area(
            "对话目标",
            value=default_goal,
            placeholder="例如：从讨论书籍/兴趣到获取联系方式/邀请读书会",
            height=100,
            key="goal_input"
        )
        
        default_language = app_config.get_setting("language", app_config.get_setting("language_options")[0])
        language = st.selectbox(
            "语言要求",
            options=app_config.get_setting("language_options"),
            index=app_config.get_setting("language_options").index(default_language) if default_language in app_config.get_setting("language_options") else 0,
            key="language_input"
        )
        
        difficulty = st.select_slider(
            "内容难度",
            options=app_config.get_setting("difficulty_options"),
            value=app_config.get_setting("default_difficulty"),
            help="CEFR语言等级: A1(入门)到C2(精通)",
            key="difficulty_input"
        )
        
        # 添加对话轮数选择
        num_turns = st.slider(
            "对话轮数",
            min_value=1,
            max_value=20,
            value=app_config.get_setting("default_num_turns"),
            help="设置对话的来回轮数，1轮=用户和AI各说一次",
            key="num_turns_input"
        )
        
        # 添加自定义单词和句型
        with st.expander("高级选项", expanded=False):
            default_custom_vocabulary = app_config.get_setting("custom_vocabulary", "")
            custom_vocabulary = st.text_area(
                "自定义单词（可选）",
                value=default_custom_vocabulary,
                placeholder="例如：Certainly, appreciate, fascinating",
                height=80,
                help="输入希望在对话中包含的单词，多个单词用逗号分隔",
                key="custom_vocabulary_input"
            )
            
            default_custom_sentence = app_config.get_setting("custom_sentence", "")
            custom_sentence = st.text_area(
                "自定义句型（可选）",
                value=default_custom_sentence,
                placeholder="例如：Would you like to..., I was wondering if...",
                height=80,
                help="输入希望在对话中使用的句型，多个句型用逗号分隔",
                key="custom_sentence_input"
            )
        
        # 添加清除按钮
        if st.button("清除默认值", key="clear_agent1"):
            st.session_state.context_input = ""
            st.session_state.goal_input = ""
            st.session_state.custom_vocabulary_input = ""
            st.session_state.custom_sentence_input = ""
        
        return {
            "context": context,
            "dialogue_mode": dialogue_mode,
            "goal": goal,
            "language": language,
            "difficulty": difficulty,
            "num_turns": num_turns,
            "custom_vocabulary": custom_vocabulary,
            "custom_sentence": custom_sentence
        }

def render_agent2_inputs(col):
    """渲染Agent 2的输入界面"""
    with col:
        st.header("Agent 2: 对话风格改编")
        
        # 用户角色特质部分
        st.subheader("用户角色特质", help="设置用户在对话中的个性特征")
        
        # 用户性格特质
        default_user_traits_chara = app_config.get_setting("user_traits_chara", "")
        user_traits_chara = st.text_area(
            "性格特质",
            value=default_user_traits_chara,
            placeholder="例如：内向，谨慎，喜欢文学...",
            height=80,
            key="user_traits_chara_input"
        )
        
        # 用户称呼方式
        default_user_traits_address = app_config.get_setting("user_traits_address", "")
        user_traits_address = st.text_area(
            "他人对用户的称呼",
            value=default_user_traits_address,
            placeholder="例如：先生，小明，老师...",
            height=80,
            key="user_traits_address_input"
        )
        
        # 用户自定义特质
        default_user_traits_custom = app_config.get_setting("user_traits_custom", "")
        user_traits_custom = st.text_area(
            "自定义特质",
            value=default_user_traits_custom,
            placeholder="例如：经常思考后再说话，说话带有哲学性...",
            height=80,
            key="user_traits_custom_input"
        )
        
        # AI角色特质部分
        st.subheader("AI角色特质", help="设置AI在对话中的个性特征")
        
        # AI性格特质
        default_ai_traits_chara = app_config.get_setting("ai_traits_chara", "")
        ai_traits_chara = st.text_area(
            "性格特质",
            value=default_ai_traits_chara,
            placeholder="例如：活泼，开朗，善于表达...",
            height=80,
            key="ai_traits_chara_input"
        )
        
        # AI口头禅
        default_ai_traits_mantra = app_config.get_setting("ai_traits_mantra", "")
        ai_traits_mantra = st.text_area(
            "口头禅",
            value=default_ai_traits_mantra,
            placeholder="例如：wow, my god, what...",
            height=80,
            key="ai_traits_mantra_input"
        )
        
        # AI语气
        default_ai_traits_tone = app_config.get_setting("ai_traits_tone", "")
        ai_traits_tone = st.text_area(
            "语气",
            value=default_ai_traits_tone,
            placeholder="例如：热情，亲切，正式，温柔...",
            height=80,
            key="ai_traits_tone_input"
        )
        
        # AI动作或神态描述语模式选择
        ai_emo_mode_options = app_config.get_setting("ai_emo_mode_options", ["自动模式", "自定义模式"])
        default_ai_emo_mode = app_config.get_setting("ai_emo_mode", "自动模式")
        ai_emo_mode = st.radio(
            "动作或神态描述语模式",
            options=ai_emo_mode_options,
            index=ai_emo_mode_options.index(default_ai_emo_mode) if default_ai_emo_mode in ai_emo_mode_options else 0,
            help="自动模式：根据句意自动配适合的动作/表情；自定义模式：使用您提供的动作/表情描述",
            key="ai_emo_mode_input",
            horizontal=True
        )
        
        # AI动作或神态描述语 - 仅在自定义模式下显示
        ai_emo = ""
        if ai_emo_mode == "自定义模式":
            default_ai_emo = app_config.get_setting("ai_emo", "")
            ai_emo = st.text_area(
                "动作或神态描述语",
                value=default_ai_emo,
                placeholder="例如：微笑着，惊讶地睁大眼睛，轻轻点头...",
                height=80,
                help="AI每句话中需要包含的动作或表情描述",
                key="ai_emo_input"
            )
        else:
            # 在自动模式下，保存一个空值，由Agent2自行生成
            ai_emo = ""
        
        # 为兼容V1版本，构建综合特质字段
        combined_user_traits = f"性格:{user_traits_chara}; 称呼:{user_traits_address}; 自定义:{user_traits_custom}"
        combined_ai_traits = f"性格:{ai_traits_chara}; 口头禅:{ai_traits_mantra}; 语气:{ai_traits_tone}"
        if ai_emo_mode == "自定义模式" and ai_emo:
            combined_ai_traits += f"; 表情/动作:{ai_emo}"
        elif ai_emo_mode == "自动模式":
            combined_ai_traits += "; 表情/动作:自动生成"
        
        # 添加清除按钮
        if st.button("清除默认值", key="clear_agent2"):
            st.session_state.user_traits_chara_input = ""
            st.session_state.user_traits_address_input = ""
            st.session_state.user_traits_custom_input = ""
            st.session_state.ai_traits_chara_input = ""
            st.session_state.ai_traits_mantra_input = ""
            st.session_state.ai_traits_tone_input = ""
            if "ai_emo_input" in st.session_state:
                st.session_state.ai_emo_input = ""
        
        return {
            # 返回详细特质
            "user_traits_chara": user_traits_chara,
            "user_traits_address": user_traits_address,
            "user_traits_custom": user_traits_custom,
            "ai_traits_chara": ai_traits_chara,
            "ai_traits_mantra": ai_traits_mantra,
            "ai_traits_tone": ai_traits_tone,
            "ai_emo": ai_emo,
            "ai_emo_mode": ai_emo_mode,
            # 兼容V1版本
            "user_traits": combined_user_traits,
            "ai_traits": combined_ai_traits
        }

def process_agent1_generation(inputs):
    """处理Agent 1的生成请求"""
    try:
        # 验证输入
        if not inputs["context"] or not inputs["goal"]:
            st.error("请至少填写对话背景和对话目标")
            return False
            
        # 获取配置和客户端
        api_provider = app_config.get_setting("api_provider")
        model = app_config.get_setting("model")
        
        # 检查API配置
        if api_provider == "openrouter" and not app_config.get_setting("openrouter_api_key"):
            st.error("请在侧边栏设置OpenRouter API密钥")
            return False
            
        # 获取代理
        client = app_config.create_api_client()
        if not client:
            st.error("创建API客户端失败，请检查API设置")
            return False
            
        # 使用agent_registry的create_agent方法创建Agent实例
        agent = agent_registry.create_agent("initial_dialogue", client, model=model, api_type=api_provider)
        if not agent:
            st.error("创建Agent失败，请检查agent_registry")
            return False
        
        with st.spinner("正在生成对话..."):
            # 处理生成请求
            result = agent.process(
                context=inputs["context"],
                dialogue_mode=inputs["dialogue_mode"],
                goal=inputs["goal"],
                language=inputs["language"],
                difficulty=inputs["difficulty"],
                num_turns=inputs["num_turns"],
                custom_vocabulary=inputs["custom_vocabulary"],
                custom_sentence=inputs["custom_sentence"]
            )
            
            if result is None:
                st.error("生成对话失败，请重试")
                return False
                
            # 检查是否是错误消息字符串
            if isinstance(result, str) and ("API" in result and "失败" in result or "error" in result.lower()):
                show_api_error(result)
                return False
                
            # 存储结果
            st.session_state.dialogue_data = result
            st.session_state.dialogue_edited = False
            
            # 保存对话数据
            saved_paths = file_manager.save_initial_dialogue(result, inputs["context"], inputs["goal"])
            if saved_paths and saved_paths[0]:
                st.session_state.saved_path = saved_paths
                st.success(f"已将结构化内容保存至:\n- JSON: {saved_paths[0]}\n- Markdown: {saved_paths[1]}")
                
                # 自动模式下直接调用Agent 2处理
                work_mode = app_config.get_setting("work_mode")
                if work_mode == "自动模式":
                    # 构建用户和AI特质数据
                    user_traits_chara = app_config.get_setting("user_traits_chara", "")
                    user_traits_address = app_config.get_setting("user_traits_address", "")
                    user_traits_custom = app_config.get_setting("user_traits_custom", "")
                    ai_traits_chara = app_config.get_setting("ai_traits_chara", "")
                    ai_traits_mantra = app_config.get_setting("ai_traits_mantra", "")
                    ai_traits_tone = app_config.get_setting("ai_traits_tone", "")
                    ai_emo = app_config.get_setting("ai_emo", "")
                    ai_emo_mode = app_config.get_setting("ai_emo_mode", "自动模式")
                    
                    # 检查特质是否已填写
                    if user_traits_chara or ai_traits_chara:
                        with st.spinner("自动模式：正在生成最终对话..."):
                            # 构建V1格式的特质字符串
                            user_traits = f"性格:{user_traits_chara}; 称呼:{user_traits_address}; 自定义:{user_traits_custom}"
                            ai_traits = f"性格:{ai_traits_chara}; 口头禅:{ai_traits_mantra}; 语气:{ai_traits_tone}"
                            if ai_emo_mode == "自定义模式" and ai_emo:
                                ai_traits += f"; 表情/动作:{ai_emo}"
                            elif ai_emo_mode == "自动模式":
                                ai_traits += "; 表情/动作:自动生成"
                            
                            # 构建Agent2的输入参数
                            agent2_inputs = {
                                "user_traits_chara": user_traits_chara,
                                "user_traits_address": user_traits_address,
                                "user_traits_custom": user_traits_custom,
                                "ai_traits_chara": ai_traits_chara,
                                "ai_traits_mantra": ai_traits_mantra,
                                "ai_traits_tone": ai_traits_tone,
                                "ai_emo": ai_emo,
                                "ai_emo_mode": ai_emo_mode,
                                "user_traits": user_traits,
                                "ai_traits": ai_traits
                            }
                            
                            # 调用Agent 2进行处理
                            process_agent2_generation(agent2_inputs)
                    else:
                        st.warning("自动模式：需要填写用户性格特质和AI性格特质才能自动生成最终对话")
            
            return True
    except Exception as e:
        st.error(f"处理生成请求时出错: {str(e)}")
        logging.error(f"处理生成请求时出错: {str(e)}", exc_info=True)
        return False

def process_agent2_generation(agent2_inputs):
    """处理Agent 2的风格改编请求"""
    try:
        # 获取配置和客户端
        api_provider = app_config.get_setting("api_provider")
        model = app_config.get_setting("model")
        language = app_config.get_setting("language")
        
        # 检查API配置
        if api_provider == "openrouter" and not app_config.get_setting("openrouter_api_key"):
            st.error("请在侧边栏设置OpenRouter API密钥")
            return False
            
        # 获取初始对话数据
        dialogue_data = st.session_state.get("dialogue_data")
        if not dialogue_data:
            st.error("没有初始对话数据，请先生成或加载对话")
            return False
            
        # 获取代理
        client = app_config.create_api_client()
        if not client:
            st.error("创建API客户端失败，请检查API设置")
            return False
            
        # 使用agent_registry的create_agent方法创建Agent实例
        agent = agent_registry.create_agent("style_adaptation", client, model=model, api_type=api_provider)
        if not agent:
            st.error("创建Agent失败，请检查agent_registry")
            return False
        
        with st.spinner("正在生成个性化对话..."):
            # 处理生成请求，传递所有需要的参数
            result = agent.process(
                dialogue_data=dialogue_data,
                user_traits_chara=agent2_inputs["user_traits_chara"],
                user_traits_address=agent2_inputs["user_traits_address"],
                user_traits_custom=agent2_inputs["user_traits_custom"],
                ai_traits_chara=agent2_inputs["ai_traits_chara"],
                ai_traits_mantra=agent2_inputs["ai_traits_mantra"],
                ai_traits_tone=agent2_inputs["ai_traits_tone"],
                ai_emo=agent2_inputs["ai_emo"],
                ai_emo_mode=agent2_inputs["ai_emo_mode"],
                language=language,
                user_traits=agent2_inputs["user_traits"],
                ai_traits=agent2_inputs["ai_traits"]
            )
            
            if result is None:
                st.error("生成个性化对话失败，请重试")
                return False
                
            # 检查是否是错误消息字符串
            if isinstance(result, str) and ("API" in result and "失败" in result or "error" in result.lower()):
                show_api_error(result)
                return False
                
            # 存储结果
            st.session_state.final_dialogue = result
            st.session_state.final_dialogue_edited = False
            
            # 构建用户和AI特质数据对象，用于保存
            user_traits_data = {
                "user_traits_chara": agent2_inputs["user_traits_chara"],
                "user_traits_address": agent2_inputs["user_traits_address"],
                "user_traits_custom": agent2_inputs["user_traits_custom"],
                "user_traits": agent2_inputs["user_traits"]
            }
            
            ai_traits_data = {
                "ai_traits_chara": agent2_inputs["ai_traits_chara"],
                "ai_traits_mantra": agent2_inputs["ai_traits_mantra"],
                "ai_traits_tone": agent2_inputs["ai_traits_tone"],
                "ai_emo": agent2_inputs["ai_emo"],
                "ai_emo_mode": agent2_inputs["ai_emo_mode"],
                "ai_traits": agent2_inputs["ai_traits"]
            }
            
            # 保存最终对话
            final_saved_paths = file_manager.save_final_dialogue(
                result,
                dialogue_data,
                agent2_inputs["user_traits"],
                agent2_inputs["ai_traits"],
                user_traits_data,
                ai_traits_data
            )
            
            if final_saved_paths and final_saved_paths[0]:
                st.session_state.final_saved_path = final_saved_paths
                st.success(f"已将最终对话内容保存至:\n- JSON: {final_saved_paths[0]}\n- Markdown: {final_saved_paths[1]}")
            
            return True
    except Exception as e:
        st.error(f"处理生成请求时出错: {str(e)}")
        logging.error(f"处理生成请求时出错: {str(e)}", exc_info=True)
        return False

def render_initial_dialogue_display():
    """渲染初始对话的显示界面"""
    if st.session_state.dialogue_data is None:
        return
    
    st.subheader("初始对话内容")
    
    # 显示保存成功消息放在生成函数中处理，这里不需要重复显示
    
    # 准备编辑器内容
    original_text = st.session_state.dialogue_data.get("original_text", "")
    key_points = st.session_state.dialogue_data.get("key_points", [])
    intentions = st.session_state.dialogue_data.get("intentions", [])
    key_vocabulary = st.session_state.dialogue_data.get("key_vocabulary", [])
    key_sentences = st.session_state.dialogue_data.get("key_sentences", [])
    
    work_mode = app_config.get_setting("work_mode")
    
    # 人机协作模式下提供编辑功能
    if work_mode == "人机协作":
        # 展示原始内容
        with st.expander("查看结构化内容", expanded=True):
            st.write("### 原始文本")
            edited_text = st.text_area("编辑对话内容", value=original_text, height=250, key="edit_text")
            
            st.write("### 关键节点")
            key_points_text = "\n".join(key_points)
            edited_key_points = st.text_area("编辑关键节点 (每行一个)", value=key_points_text, height=150, key="edit_key_points")
            
            st.write("### 对话意图")
            intentions_text = "\n".join(intentions)
            edited_intentions = st.text_area("编辑对话意图 (每行一个)", value=intentions_text, height=150, key="edit_intentions")
            
            st.write("### 关键情节词汇")
            key_vocabulary_text = "\n".join(key_vocabulary)
            edited_key_vocabulary = st.text_area("编辑关键情节词汇 (每行一个)", value=key_vocabulary_text, height=150, key="edit_key_vocabulary")
            
            st.write("### 关键情节句型")
            key_sentences_text = "\n".join(key_sentences)
            edited_key_sentences = st.text_area("编辑关键情节句型 (每行一个)", value=key_sentences_text, height=150, key="edit_key_sentences")
            
            # 处理编辑后的内容
            edited_key_points_list = [p.strip() for p in edited_key_points.split("\n") if p.strip()]
            edited_intentions_list = [i.strip() for i in edited_intentions.split("\n") if i.strip()]
            edited_key_vocabulary_list = [v.strip() for v in edited_key_vocabulary.split("\n") if v.strip()]
            edited_key_sentences_list = [s.strip() for s in edited_key_sentences.split("\n") if s.strip()]
            
            # 更新编辑状态
            if (edited_text != original_text or 
                edited_key_points_list != key_points or 
                edited_intentions_list != intentions or
                edited_key_vocabulary_list != key_vocabulary or
                edited_key_sentences_list != key_sentences):
                st.session_state.dialogue_edited = True
                
                # 更新编辑后的对话数据
                edited_dialogue_data = {
                    "original_text": edited_text,
                    "key_points": edited_key_points_list,
                    "intentions": edited_intentions_list,
                    "key_vocabulary": edited_key_vocabulary_list,
                    "key_sentences": edited_key_sentences_list
                }
                st.session_state.dialogue_data = edited_dialogue_data
            
            # 确认按钮
            if st.button("确认编辑", key="confirm_edit_initial_dialogue"):
                st.success("已更新对话内容")
                
                # 如果已编辑，重新保存
                if st.session_state.dialogue_edited:
                    context = app_config.get_setting("context")
                    goal = app_config.get_setting("goal")
                    saved_paths = file_manager.update_initial_dialogue(
                        st.session_state.saved_path[0], 
                        st.session_state.dialogue_data, 
                        context, 
                        goal
                    )
                    if saved_paths:
                        st.session_state.saved_path = saved_paths
                        st.success(f"已将编辑后的结构化内容保存至: {saved_paths[0]} 和 {saved_paths[1]}")
    else:
        # 自动模式下仅显示结构化内容
        with st.expander("查看初始对话", expanded=True):
            st.write(original_text)
            
            if key_points:
                st.subheader("关键节点")
                for point in key_points:
                    st.markdown(f"- {point}")
            
            if intentions:
                st.subheader("对话意图")
                for intent in intentions:
                    st.markdown(f"- {intent}")
                    
            if key_vocabulary:
                st.subheader("关键情节词汇")
                for vocab in key_vocabulary:
                    st.markdown(f"- {vocab}")
                    
            if key_sentences:
                st.subheader("关键情节句型")
                for sentence in key_sentences:
                    st.markdown(f"- {sentence}")

def render_final_dialogue_display():
    """渲染最终对话的显示界面"""
    if 'final_dialogue' not in st.session_state or not st.session_state.final_dialogue:
        return
    
    st.subheader("最终对话 (风格化)")
    
    # 编辑和实时更新功能
    with st.expander("编辑最终对话", expanded=True):
        edited_final_dialogue = st.text_area(
            "编辑最终对话内容", 
            value=st.session_state.final_dialogue, 
            height=300,
            key="edit_final_dialogue"
        )
        
        # 更新编辑状态
        if edited_final_dialogue != st.session_state.final_dialogue:
            st.session_state.final_dialogue = edited_final_dialogue
            st.session_state.final_dialogue_edited = True
        
        # 确认按钮
        if st.button("确认编辑", key="confirm_edit_final_dialogue"):
            if st.session_state.final_dialogue_edited:
                # 更新最终对话内容文件
                if st.session_state.final_saved_path:
                    # 获取最新的特质数据
                    user_traits_data = {
                        "user_traits_chara": app_config.get_setting("user_traits_chara", ""),
                        "user_traits_address": app_config.get_setting("user_traits_address", ""),
                        "user_traits_custom": app_config.get_setting("user_traits_custom", ""),
                        "user_traits": app_config.get_setting("user_traits", "")
                    }
                    
                    ai_traits_data = {
                        "ai_traits_chara": app_config.get_setting("ai_traits_chara", ""),
                        "ai_traits_mantra": app_config.get_setting("ai_traits_mantra", ""),
                        "ai_traits_tone": app_config.get_setting("ai_traits_tone", ""),
                        "ai_emo": app_config.get_setting("ai_emo", ""),
                        "ai_emo_mode": app_config.get_setting("ai_emo_mode", "自动模式"),
                        "ai_traits": app_config.get_setting("ai_traits", "")
                    }
                    
                    # 构建V1兼容的特质字符串（如果V2详细特质存在则使用它们构建）
                    user_traits = user_traits_data["user_traits"]
                    ai_traits = ai_traits_data["ai_traits"]
                    
                    # 如果有V2格式的详细特质但没有V1格式的综合特质，则构建V1格式
                    if not user_traits and (user_traits_data["user_traits_chara"] or user_traits_data["user_traits_address"] or user_traits_data["user_traits_custom"]):
                        user_traits = f"性格:{user_traits_data['user_traits_chara']}; 称呼:{user_traits_data['user_traits_address']}; 自定义:{user_traits_data['user_traits_custom']}"
                    
                    if not ai_traits and (ai_traits_data["ai_traits_chara"] or ai_traits_data["ai_traits_mantra"] or ai_traits_data["ai_traits_tone"]):
                        ai_traits = f"性格:{ai_traits_data['ai_traits_chara']}; 口头禅:{ai_traits_data['ai_traits_mantra']}; 语气:{ai_traits_data['ai_traits_tone']}"
                        # 根据表情模式添加不同的表情描述
                        if ai_traits_data["ai_emo_mode"] == "自定义模式" and ai_traits_data["ai_emo"]:
                            ai_traits += f"; 表情/动作:{ai_traits_data['ai_emo']}"
                        elif ai_traits_data["ai_emo_mode"] == "自动模式":
                            ai_traits += "; 表情/动作:自动生成"
                    
                    updated_paths = file_manager.update_final_dialogue(
                        st.session_state.final_saved_path[0],
                        st.session_state.final_dialogue,
                        st.session_state.dialogue_data,
                        user_traits,
                        ai_traits,
                        # 添加V2格式的特质数据
                        user_traits_data,
                        ai_traits_data
                    )
                    if updated_paths:
                        st.session_state.final_saved_path = updated_paths
                        st.success(f"已将编辑后的最终对话内容保存至: {updated_paths[0]} 和 {updated_paths[1]}")
                else:
                    # 如果没有保存过，则保存
                    # 获取最新的特质数据
                    user_traits_data = {
                        "user_traits_chara": app_config.get_setting("user_traits_chara", ""),
                        "user_traits_address": app_config.get_setting("user_traits_address", ""),
                        "user_traits_custom": app_config.get_setting("user_traits_custom", ""),
                        "user_traits": app_config.get_setting("user_traits", "")
                    }
                    
                    ai_traits_data = {
                        "ai_traits_chara": app_config.get_setting("ai_traits_chara", ""),
                        "ai_traits_mantra": app_config.get_setting("ai_traits_mantra", ""),
                        "ai_traits_tone": app_config.get_setting("ai_traits_tone", ""),
                        "ai_emo": app_config.get_setting("ai_emo", ""),
                        "ai_emo_mode": app_config.get_setting("ai_emo_mode", "自动模式"),
                        "ai_traits": app_config.get_setting("ai_traits", "")
                    }
                    
                    # 构建V1兼容的特质字符串
                    user_traits = user_traits_data["user_traits"]
                    ai_traits = ai_traits_data["ai_traits"]
                    
                    # 如果有V2格式的详细特质但没有V1格式的综合特质，则构建V1格式
                    if not user_traits and (user_traits_data["user_traits_chara"] or user_traits_data["user_traits_address"] or user_traits_data["user_traits_custom"]):
                        user_traits = f"性格:{user_traits_data['user_traits_chara']}; 称呼:{user_traits_data['user_traits_address']}; 自定义:{user_traits_data['user_traits_custom']}"
                    
                    if not ai_traits and (ai_traits_data["ai_traits_chara"] or ai_traits_data["ai_traits_mantra"] or ai_traits_data["ai_traits_tone"]):
                        ai_traits = f"性格:{ai_traits_data['ai_traits_chara']}; 口头禅:{ai_traits_data['ai_traits_mantra']}; 语气:{ai_traits_data['ai_traits_tone']}"
                        # 根据表情模式添加不同的表情描述
                        if ai_traits_data["ai_emo_mode"] == "自定义模式" and ai_traits_data["ai_emo"]:
                            ai_traits += f"; 表情/动作:{ai_traits_data['ai_emo']}"
                        elif ai_traits_data["ai_emo_mode"] == "自动模式":
                            ai_traits += "; 表情/动作:自动生成"
                    
                    final_saved_paths = file_manager.save_final_dialogue(
                        st.session_state.final_dialogue,
                        st.session_state.dialogue_data,
                        user_traits,
                        ai_traits,
                        # 添加V2格式的特质数据
                        user_traits_data,
                        ai_traits_data
                    )
                    if final_saved_paths:
                        st.session_state.final_saved_path = final_saved_paths
                        st.success(f"已将编辑后的最终对话内容保存至: {final_saved_paths[0]} 和 {final_saved_paths[1]}")
                st.success("已更新最终对话内容")

def main():
    # 标题
    st.title("Carl的课程内容创作Agents👫🏻")
    
    # 渲染侧边栏
    render_sidebar()
    
    # 创建两列布局
    col1, col2 = st.columns(2)
    
    # 渲染Agent输入界面
    agent1_inputs = render_agent1_inputs(col1)
    agent2_inputs = render_agent2_inputs(col2)
    
    # 保存输入到配置
    for key, value in agent1_inputs.items():
        app_config.set_setting(key, value)
    
    for key, value in agent2_inputs.items():
        app_config.set_setting(key, value)
    
    # 分阶段按钮和状态管理
    col_buttons = st.columns(2)
    
    # 生成初始对话按钮
    with col_buttons[0]:
        if st.button("生成初始对话", type="primary"):
            process_agent1_generation(agent1_inputs)
    
    # 生成最终对话按钮
    with col_buttons[1]:
        work_mode = app_config.get_setting("work_mode")
        if work_mode == "人机协作":
            button_text = "生成优化对话"
        else:
            button_text = "生成最终对话"
            
        if st.button(button_text, type="primary"):
            process_agent2_generation(agent2_inputs)
    
    # 显示初始对话内容
    render_initial_dialogue_display()
    
    # 显示最终对话内容
    render_final_dialogue_display()

if __name__ == "__main__":
    main()
