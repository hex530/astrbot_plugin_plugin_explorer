from astrbot.api.star import Context, Star, register
from astrbot.api.all import *
import aiohttp
import logging
import os
import subprocess

logger = logging.getLogger("astrbot")

@register("plugin_explorer", "夕小柠 & 陆渊", "智能插件管家：支持 Token 加速搜索与一键安装。", "1.1.2")
class PluginExplorer(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config

    def _is_admin(self, event: AstrMessageEvent):
        admin_qq = str(self.config.get("admin_qq", "1591793025"))
        return str(event.get_sender_id()) == admin_qq

    def _get_headers(self):
        headers = {"Accept": "application/vnd.github.v3+json"}
        token = self.config.get("github_token", "").strip()
        if token:
            headers["Authorization"] = f"token {token}"
        return headers

    @llm_tool(name="search_github_plugins")
    async def search_github_plugins(self, event: AstrMessageEvent, keyword: str):
        """
        在 GitHub 上搜索 AstrBot 插件。
        参数 keyword: 搜索关键词。
        """
        if not self._is_admin(event):
            return "权限不足。"

        query = f"{keyword}+topic:astrbot-plugin"
        url = f"https://api.github.com/search/repositories?q={query}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as resp:
                if resp.status == 403:
                    return "❌ GitHub 访问受限。请检查 Token。"
                if resp.status != 200:
                    return f"❌ 搜索失败 (状态码: {resp.status})"
                
                data = await resp.json()
                items = data.get('items', [])[:3]
                
                if not items: return f"没搜到关于‘{keyword}’的插件。"
                
                limit = self.config.get("readme_summary_limit", 200)
                report = f"🔍 搜到了以下插件：\n"
                for item in items:
                    full_name = item['full_name']
                    desc = item['description'] or "无描述"
                    readme_url = f"https://raw.githubusercontent.com/{full_name}/main/README.md"
                    readme_content = "（文档摘要获取中...）"
                    
                    async with session.get(readme_url, headers=self._get_headers()) as r_resp:
                        if r_resp.status == 200:
                            readme_text = await r_resp.text()
                            readme_content = readme_text[:limit].replace('\n', ' ') + "..."
                    
                    report += f"\n📦 【{full_name}】\n📝 简介: {desc}\n📖 摘要: {readme_content}\n🔗 URL: {item['html_url']}\n"
                
                return report

    @llm_tool(name="install_plugin_direct")
    async def install_plugin_direct(self, event: AstrMessageEvent, repo_url: str):
        """
        直接安装指定的 GitHub 插件。
        """
        if not self._is_admin(event):
            return "权限不足。"

        plugin_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
        base_path = os.path.abspath(os.path.join(os.getcwd(), "data/plugins"))
        target_path = os.path.join(base_path, plugin_name)

        if os.path.exists(target_path):
            return f"插件 {plugin_name} 已存在。"

        try:
            process = subprocess.run(['git', 'clone', '--depth', '1', repo_url, target_path], capture_output=True, text=True)
            if process.returncode == 0:
                return f"✅ 成功！插件 {plugin_name} 已安装。请重启 AstrBot。"
            else:
                return f"❌ 失败：{process.stderr}"
        except Exception as e:
            return f"❌ 出错：{str(e)}"
