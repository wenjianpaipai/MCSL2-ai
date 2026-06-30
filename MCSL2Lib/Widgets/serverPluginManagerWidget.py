# Copyright 2024, MCSL Team, mailto:services@mcsl.com.cn
#
# Part of "MCSL2", a simple and multifunctional Minecraft server launcher.
#
# Licensed under the GNU General Public License, Version 3.0, with our
# additional agreements. (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://github.com/MCSLTeam/MCSL2/raw/master/LICENSE
#
################################################################################
"""
服务器插件管理器 - 内嵌版本
"""

import json
import os
import re
import shutil
import zipfile
from os import path as osp
from typing import Dict, List, Optional, Set

from PyQt5.QtCore import Qt, QSize, QTimer, QUrl
from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QFileDialog,
)
from PyQt5.QtGui import QDesktopServices
from qfluentwidgets import (
    PrimaryPushButton,
    PushButton,
    TitleLabel,
    StrongBodyLabel,
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    TextEdit,
    SwitchButton,
    MessageBox,
    InfoBar,
    InfoBarPosition,
    FluentIcon as FIF,
    ToolButton,
    Dialog,
)

from MCSL2Lib.utils import readFile, writeFile, MCSL2Logger, openLocalFile


# ==================== 工具函数 ====================

def get_server_plugins_folder(server_name: str) -> str:
    """获取服务器插件文件夹路径"""
    return osp.join("Servers", server_name, "plugins")


def read_plugin_yml(jar_path: str) -> Optional[dict]:
    """从 jar 文件中读取 plugin.yml"""
    try:
        with zipfile.ZipFile(jar_path, 'r') as zf:
            if 'plugin.yml' in zf.namelist():
                content = zf.read('plugin.yml').decode('utf-8', errors='ignore')
                result = {}
                for line in content.split('\n'):
                    line = line.strip()
                    if ':' in line and not line.startswith('#') and not line.startswith('-'):
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]
                            result[key] = value
                return result
    except Exception:
        pass
    return None


def extract_version_from_jar(jar_path: str) -> str:
    """从 jar 文件中提取版本号"""
    plugin_yml = read_plugin_yml(jar_path)
    if plugin_yml and 'version' in plugin_yml:
        ver = plugin_yml['version']
        if ver and ver != "${project.version}":
            return ver
    basename = osp.basename(jar_path)
    match = re.search(r'[-_vV](\d+(?:\.\d+)+)', basename)
    if match:
        return match.group(1)
    return "未知"


def extract_plugin_name_from_jar(jar_path: str) -> str:
    """从 jar 文件中提取插件名称"""
    plugin_yml = read_plugin_yml(jar_path)
    if plugin_yml and 'name' in plugin_yml:
        name = plugin_yml['name']
        if name and name != "${project.name}":
            return name
    return ""


def extract_description_from_jar(jar_path: str) -> str:
    """从 jar 文件中提取插件描述"""
    plugin_yml = read_plugin_yml(jar_path)
    if plugin_yml and 'description' in plugin_yml:
        desc = plugin_yml['description']
        if desc and desc != "${project.description}":
            return desc
    return ""


def extract_plugin_id_from_filename(filename: str) -> str:
    """从文件名中提取插件ID（去掉版本号）"""
    name = osp.splitext(filename)[0]
    match = re.match(r'^(.+?)[-_][vV]?\d+(?:\.\d+)*$', name)
    if match:
        return match.group(1)
    return name


def get_plugin_config_path(server_name: str) -> str:
    """获取插件配置文件的保存路径"""
    config_dir = osp.join("MCSL2", "PluginManager", "data")
    os.makedirs(config_dir, exist_ok=True)
    return osp.join(config_dir, f"{server_name}_plugins.json")


def load_plugin_data(server_name: str) -> Dict[str, dict]:
    """加载插件的自定义数据"""
    config_path = get_plugin_config_path(server_name)
    if osp.exists(config_path):
        try:
            content = readFile(config_path)
            return json.loads(content)
        except Exception:
            pass
    return {}


def save_plugin_data(server_name: str, data: Dict[str, dict]):
    """保存插件的自定义数据"""
    config_path = get_plugin_config_path(server_name)
    try:
        writeFile(config_path, json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        MCSL2Logger.error(f"保存插件数据失败: {e}")


def scan_plugins(server_name: str) -> List[dict]:
    """扫描服务器插件文件夹"""
    plugins_folder = get_server_plugins_folder(server_name)
    if not osp.exists(plugins_folder):
        return []

    saved_data = load_plugin_data(server_name)
    plugins = []

    for filename in os.listdir(plugins_folder):
        if not filename.endswith('.jar') and not filename.endswith('.jar.disabled'):
            continue

        file_path = osp.join(plugins_folder, filename)
        is_enabled = filename.endswith('.jar')
        real_name = filename.replace('.disabled', '') if not is_enabled else filename

        plugin_id = extract_plugin_id_from_filename(real_name)
        saved = saved_data.get(plugin_id, {})

        auto_version = extract_version_from_jar(file_path)
        auto_plugin_name = extract_plugin_name_from_jar(file_path)
        auto_description = extract_description_from_jar(file_path)

        plugin_info = {
            "id": plugin_id,
            "filename": real_name,
            "display_name": saved.get("display_name", auto_plugin_name or plugin_id),
            "is_enabled": is_enabled,
            "version": auto_version,
            "history_versions": saved.get("history_versions", ""),
            "description": saved.get("description", auto_description),
            "doc_url": saved.get("doc_url", ""),
            "auto_version": auto_version,
            "auto_name": auto_plugin_name,
            "saved_version": saved.get("version", ""),
        }
        plugins.append(plugin_info)

    plugins.sort(key=lambda x: x["filename"].lower())
    return plugins


def toggle_plugin_enabled(server_name: str, filename: str, enabled: bool) -> bool:
    """切换插件启用状态"""
    plugins_folder = get_server_plugins_folder(server_name)
    old_name = f"{filename}.disabled" if enabled else filename
    new_name = filename if enabled else f"{filename}.disabled"
    old_path = osp.join(plugins_folder, old_name)
    new_path = osp.join(plugins_folder, new_name)

    if osp.exists(old_path):
        try:
            os.rename(old_path, new_path)
            return True
        except Exception as e:
            MCSL2Logger.error(f"切换插件状态失败: {e}")
    return False


def check_duplicate_enabled_plugins(plugins: List[dict]) -> List[tuple]:
    """检查是否有同名插件同时启用"""
    enabled_map: Dict[str, List[str]] = {}
    for plugin in plugins:
        if plugin["is_enabled"]:
            pid = plugin["id"]
            if pid not in enabled_map:
                enabled_map[pid] = []
            enabled_map[pid].append(plugin["version"])

    conflicts = []
    for pid, versions in enabled_map.items():
        if len(versions) > 1:
            conflicts.append((pid, versions))
    return conflicts


def update_history_versions(server_name: str, plugins: List[dict]) -> List[dict]:
    """检查版本变化，自动更新历史版本记录"""
    saved_data = load_plugin_data(server_name)
    updated = False

    plugin_versions: Dict[str, List[str]] = {}
    for plugin in plugins:
        pid = plugin["id"]
        if pid not in plugin_versions:
            plugin_versions[pid] = []
        plugin_versions[pid].append(plugin["version"])

    for plugin in plugins:
        plugin_id = plugin["id"]
        current_version = plugin["version"]
        saved_version = plugin.get("saved_version", "")

        old_data = saved_data.get(plugin_id, {})
        old_history = old_data.get("history_versions", "")

        if saved_version and saved_version != current_version:
            history_set: Set[str] = set()
            if old_history:
                for v in old_history.split(','):
                    v = v.strip()
                    if v:
                        history_set.add(v)

            if saved_version != current_version:
                history_set.add(saved_version)

            for ver in plugin_versions.get(plugin_id, []):
                if ver != current_version:
                    history_set.add(ver)

            new_history = ', '.join(sorted(history_set, key=lambda x: [int(n) for n in re.findall(r'\d+', x)], reverse=True))
            plugin["history_versions"] = new_history

            if plugin_id not in saved_data:
                saved_data[plugin_id] = {}
            saved_data[plugin_id]["history_versions"] = new_history
            saved_data[plugin_id]["version"] = current_version
            for key in ["display_name", "description", "doc_url"]:
                if key in old_data:
                    saved_data[plugin_id][key] = old_data[key]
            updated = True
        else:
            plugin["history_versions"] = old_history
            if plugin_id not in saved_data:
                saved_data[plugin_id] = {}
            saved_data[plugin_id]["version"] = current_version
            for key in ["display_name", "description", "doc_url", "history_versions"]:
                if key in old_data:
                    saved_data[plugin_id][key] = old_data[key]
            updated = True

    if updated:
        save_plugin_data(server_name, saved_data)

    return plugins


# ==================== UI 组件 ====================

class PluginDetailDialog(Dialog):
    """插件详情编辑对话框"""

    def __init__(self, plugin_info: dict, parent=None):
        self.plugin_info = plugin_info
        self.result_data = None
        super().__init__("编辑插件信息", "", parent)
        self.setupUI()

    def setupUI(self):
        self.textLayout.setSpacing(10)

        filename_layout = QHBoxLayout()
        filename_layout.addWidget(StrongBodyLabel("文件名:", self))
        filename_label = BodyLabel(self.plugin_info["filename"], self)
        filename_layout.addWidget(filename_label, 1)
        self.textLayout.addLayout(filename_layout)

        auto_ver_layout = QHBoxLayout()
        auto_ver_layout.addWidget(StrongBodyLabel("自动识别版本:", self))
        auto_ver = self.plugin_info.get("auto_version", "未知")
        auto_ver_label = BodyLabel(auto_ver, self)
        auto_ver_layout.addWidget(auto_ver_label, 1)
        self.textLayout.addLayout(auto_ver_layout)

        name_layout = QHBoxLayout()
        name_layout.addWidget(StrongBodyLabel("显示名称:", self))
        self.nameEdit = LineEdit(self)
        self.nameEdit.setText(self.plugin_info.get("display_name", ""))
        self.nameEdit.setPlaceholderText("插件的中文名称或自定义名称")
        name_layout.addWidget(self.nameEdit, 1)
        self.textLayout.addLayout(name_layout)

        ver_layout = QHBoxLayout()
        ver_layout.addWidget(StrongBodyLabel("版本号:", self))
        self.verEdit = LineEdit(self)
        self.verEdit.setText(self.plugin_info.get("version", ""))
        self.verEdit.setPlaceholderText("可手动修改版本号")
        ver_layout.addWidget(self.verEdit, 1)
        self.textLayout.addLayout(ver_layout)

        history_layout = QHBoxLayout()
        history_layout.addWidget(StrongBodyLabel("历史版本:", self))
        self.historyEdit = LineEdit(self)
        self.historyEdit.setText(self.plugin_info.get("history_versions", ""))
        self.historyEdit.setPlaceholderText("如: 1.0, 1.1, 1.2")
        history_layout.addWidget(self.historyEdit, 1)
        self.textLayout.addLayout(history_layout)

        doc_layout = QHBoxLayout()
        doc_layout.addWidget(StrongBodyLabel("文档链接:", self))
        self.docEdit = LineEdit(self)
        self.docEdit.setText(self.plugin_info.get("doc_url", ""))
        self.docEdit.setPlaceholderText("https://...")
        doc_layout.addWidget(self.docEdit, 1)
        self.textLayout.addLayout(doc_layout)

        self.textLayout.addWidget(StrongBodyLabel("详细介绍:", self))
        self.descEdit = TextEdit(self)
        self.descEdit.setText(self.plugin_info.get("description", ""))
        self.descEdit.setPlaceholderText("插件的详细介绍...")
        self.descEdit.setMinimumHeight(100)
        self.textLayout.addWidget(self.descEdit)

        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")
        self.yesSignal.connect(self.onSave)

    def onSave(self):
        self.result_data = {
            "display_name": self.nameEdit.text().strip(),
            "version": self.verEdit.text().strip(),
            "history_versions": self.historyEdit.text().strip(),
            "doc_url": self.docEdit.text().strip(),
            "description": self.descEdit.toPlainText().strip(),
        }


class PluginManagerPage(QWidget):
    """插件管理页面"""

    def __init__(self, server_name: str, parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self.plugins_data = {}
        self.setupUI()
        self.refreshPlugins()

    def setupUI(self):
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)

        self.titleWidget = QWidget(self)
        title_layout = QVBoxLayout(self.titleWidget)
        title_layout.setContentsMargins(0, 0, 0, 0)

        self.titleLabel = TitleLabel(f"插件管理 - {self.server_name}", self.titleWidget)
        title_layout.addWidget(self.titleLabel)

        self.subTitleLabel = StrongBodyLabel(
            "管理和编辑服务器插件，支持启用/禁用和自定义信息", self.titleWidget
        )
        title_layout.addWidget(self.subTitleLabel)

        self.layout.addWidget(self.titleWidget, 0, 0, 1, 1)

        btn_widget = QWidget(self)
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.refreshBtn = PushButton(FIF.SYNC, "刷新", btn_widget)
        self.refreshBtn.clicked.connect(self.refreshPlugins)
        btn_layout.addWidget(self.refreshBtn)

        self.openFolderBtn = PushButton(FIF.FOLDER, "打开插件文件夹", btn_widget)
        self.openFolderBtn.clicked.connect(self.openPluginsFolder)
        btn_layout.addWidget(self.openFolderBtn)

        self.importBtn = PushButton(FIF.DOWNLOAD, "导入插件", btn_widget)
        self.importBtn.clicked.connect(self.importPlugin)
        btn_layout.addWidget(self.importBtn)

        btn_layout.addStretch(1)

        self.layout.addWidget(btn_widget, 1, 0, 1, 1)

        self.contentWidget = QWidget(self)
        self.contentLayout = QGridLayout(self.contentWidget)
        self.contentLayout.setContentsMargins(0, 0, 0, 0)

        # 使用 QStackedWidget 管理表格和空状态
        from PyQt5.QtWidgets import QStackedWidget
        self.contentStack = QStackedWidget(self.contentWidget)
        self.contentLayout.addWidget(self.contentStack, 0, 0, 1, 1)

        self.table = QTableWidget(self.contentStack)
        ...
        self.contentStack.addWidget(self.table)

        self.emptyWidget = QWidget(self.contentStack)
        empty_layout = QVBoxLayout(self.emptyWidget)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_label = SubtitleLabel("暂无插件", self.emptyWidget)
        empty_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_label)
        empty_tip = BodyLabel(
            f"该服务器 plugins 文件夹为空，或文件夹不存在。\n请将插件放入 Servers/{self.server_name}/plugins/ 文件夹",
            self.emptyWidget,
        )
        empty_tip.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_tip)
        self.contentStack.addWidget(self.emptyWidget)

        self.emptyWidget = QWidget(self.contentWidget)
        empty_layout = QVBoxLayout(self.emptyWidget)
        empty_layout.setAlignment(Qt.AlignCenter)

        empty_label = SubtitleLabel("暂无插件", self.emptyWidget)
        empty_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_label)

        empty_tip = BodyLabel(
            f"该服务器 plugins 文件夹为空，或文件夹不存在。\n请将插件放入 Servers/{self.server_name}/plugins/ 文件夹",
            self.emptyWidget,
        )
        empty_tip.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_tip)

        self.contentLayout.addWidget(self.emptyWidget, 0, 0, 1, 1)

        self.layout.addWidget(self.contentWidget, 2, 0, 1, 1)

    def refreshPlugins(self):
        """刷新插件列表"""
        plugins = scan_plugins(self.server_name)
        plugins = update_history_versions(self.server_name, plugins)

        conflicts = check_duplicate_enabled_plugins(plugins)
        if conflicts:
            for plugin_id, versions in conflicts:
                QTimer.singleShot(100, lambda pid=plugin_id, vers=versions: self._show_conflict_warning(pid, vers))

        self.plugins_data = {p["filename"]: p for p in plugins}

        if not plugins:
            self.contentStack.setCurrentIndex(1)  # 显示 emptyWidget
            return

        self.contentStack.setCurrentIndex(0)  # 显示 table
        self.table.setRowCount(len(plugins))

        for row, plugin in enumerate(plugins):
            switch = SwitchButton(self.table)
            switch.setChecked(plugin["is_enabled"])
            switch.checkedChanged.connect(
                lambda checked, fname=plugin["filename"]: self.onToggleEnabled(fname, checked)
            )
            self.table.setCellWidget(row, 0, switch)

            filename_item = QTableWidgetItem(plugin["filename"])
            filename_item.setData(Qt.UserRole, plugin["id"])
            self.table.setItem(row, 1, filename_item)

            display_name = plugin["display_name"] or plugin["id"]
            name_item = QTableWidgetItem(display_name)
            self.table.setItem(row, 2, name_item)

            ver_item = QTableWidgetItem(plugin["version"])
            self.table.setItem(row, 3, ver_item)

            history_item = QTableWidgetItem(plugin["history_versions"])
            self.table.setItem(row, 4, history_item)

            doc_url = plugin["doc_url"]
            if doc_url:
                doc_item = QTableWidgetItem(doc_url)
                doc_item.setForeground(Qt.blue)
                doc_item.setToolTip(f"点击打开: {doc_url}")
            else:
                doc_item = QTableWidgetItem("")
            self.table.setItem(row, 5, doc_item)

            btn_widget = QWidget(self.table)
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(4)

            edit_btn = ToolButton(FIF.EDIT, btn_widget)
            edit_btn.setToolTip("编辑详情")
            edit_btn.setFixedSize(28, 28)
            edit_btn.clicked.connect(lambda checked, fname=plugin["filename"]: self.onEditPlugin(fname))
            btn_layout.addWidget(edit_btn)

            detail_btn = ToolButton(FIF.INFO, btn_widget)
            detail_btn.setToolTip("查看详情")
            detail_btn.setFixedSize(28, 28)
            detail_btn.clicked.connect(lambda checked, fname=plugin["filename"]: self.onViewDetail(fname))
            btn_layout.addWidget(detail_btn)

            btn_layout.addStretch(1)
            self.table.setCellWidget(row, 6, btn_widget)

        self.table.itemClicked.connect(self.onTableItemClicked)

    def onTableItemClicked(self, item: QTableWidgetItem):
        """处理表格点击事件"""
        if item.column() == 5:
            url_text = item.text()
            if url_text:
                if not url_text.startswith(('http://', 'https://')):
                    url_text = 'https://' + url_text
                QDesktopServices.openUrl(QUrl(url_text))

    def _show_conflict_warning(self, plugin_id: str, versions: List[str]):
        """显示冲突警告"""
        try:
            box = MessageBox(
                "插件冲突警告",
                f"检测到同名插件同时启用：\n插件ID: {plugin_id}\n版本: {', '.join(versions)}\n\n请禁用其中一个版本以避免冲突！",
                self,
            )
            box.yesButton.setText("知道了")
            box.cancelButton.setParent(None)
            box.cancelButton.deleteLater()
            box.exec()
        except Exception as e:
            MCSL2Logger.error(f"显示冲突警告失败: {e}")

    def onToggleEnabled(self, filename: str, enabled: bool):
        """切换插件启用状态"""
        plugin = self.plugins_data.get(filename)
        if not plugin:
            return

        plugin_id = plugin["id"]

        if toggle_plugin_enabled(self.server_name, filename, enabled):
            plugin["is_enabled"] = enabled
            status = "启用" if enabled else "禁用"
            InfoBar.success(
                "操作成功",
                f"已{status}插件: {plugin_id}",
                parent=self,
                duration=2000,
            )
            self.refreshPlugins()
        else:
            InfoBar.error(
                "操作失败",
                f"无法切换插件状态: {plugin_id}",
                parent=self,
                duration=3000,
            )
            self.refreshPlugins()

    def onEditPlugin(self, filename: str):
        """编辑插件信息"""
        plugin = self.plugins_data.get(filename)
        if not plugin:
            return

        plugin_id = plugin["id"]

        dialog = PluginDetailDialog(plugin, self)
        if dialog.exec():
            if dialog.result_data:
                saved_data = load_plugin_data(self.server_name)
                saved_data[plugin_id] = dialog.result_data
                saved_data[plugin_id]["version"] = plugin["version"]
                save_plugin_data(self.server_name, saved_data)
                self.refreshPlugins()

                InfoBar.success(
                    "保存成功",
                    f"插件 {plugin_id} 的信息已更新",
                    parent=self,
                    duration=2000,
                )

    def onViewDetail(self, filename: str):
        """查看插件详情"""
        plugin = self.plugins_data.get(filename)
        if not plugin:
            return

        plugin_id = plugin["id"]

        content = f"""文件名: {plugin['filename']}
显示名称: {plugin['display_name'] or '未设置'}
自动识别名称: {plugin.get('auto_name', '无')}
版本号: {plugin['version']}
自动识别版本: {plugin.get('auto_version', '未知')}
历史版本: {plugin['history_versions'] or '无'}
文档链接: {plugin['doc_url'] or '无'}
状态: {'已启用' if plugin['is_enabled'] else '已禁用'}

详细介绍:
{plugin['description'] or '暂无介绍'}"""

        dialog = MessageBox(
            f"插件详情 - {plugin_id}",
            content,
            self,
        )
        dialog.yesButton.setText("关闭")
        dialog.cancelButton.setParent(None)
        dialog.cancelButton.deleteLater()
        dialog.exec()

    def openPluginsFolder(self):
        """打开插件文件夹"""
        folder = get_server_plugins_folder(self.server_name)
        os.makedirs(folder, exist_ok=True)
        openLocalFile(folder)

    def importPlugin(self):
        """导入插件文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择插件文件",
            "",
            "JAR 文件 (*.jar);;所有文件 (*)"
        )
        if not files:
            return

        plugins_folder = get_server_plugins_folder(self.server_name)
        os.makedirs(plugins_folder, exist_ok=True)

        imported = 0
        for file_path in files:
            try:
                filename = osp.basename(file_path)
                target = osp.join(plugins_folder, filename)
                if osp.exists(target):
                    box = MessageBox(
                        "文件已存在",
                        f"插件 {filename} 已存在，是否覆盖？",
                        self,
                    )
                    box.yesButton.setText("覆盖")
                    box.cancelButton.setText("跳过")
                    if box.exec() != 1:
                        continue
                shutil.copy2(file_path, target)
                imported += 1
            except Exception as e:
                MCSL2Logger.error(f"导入插件失败: {e}")

        if imported > 0:
            InfoBar.success(
                "导入成功",
                f"已导入 {imported} 个插件",
                parent=self,
                duration=2000,
            )
            self.refreshPlugins()