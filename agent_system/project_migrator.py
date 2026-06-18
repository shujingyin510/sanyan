"""跨项目迁移器 — 规则/模板导出导入

功能：
  1. 导出规则和模板到单个包文件
  2. 从包文件导入规则和模板
  3. 支持选择性导出（只导出特定规则/模板）

用法：
  # 导出
  migrator = ProjectMigrator()
  migrator.export_rules('my_rules.tar.gz', include_templates=True)

  # 导入
  migrator.import_rules('my_rules.tar.gz', overwrite=False)
"""

import json
import os
import shutil
import tarfile
import tempfile
from typing import Dict, List, Optional


class ProjectMigrator:
    """跨项目迁移器"""

    def __init__(self, project_root: str = '.'):
        self.project_root = project_root
        self.rules_file = os.path.join(project_root, 'agent_rules.md')
        self.templates_dir = os.path.join(project_root, 'agent_system', 'templates')
        self.styles_file = os.path.join(project_root, 'agent_system', 'learned_styles.md')

    def export_rules(
        self,
        output_path: str,
        include_templates: bool = True,
        include_styles: bool = True,
        rule_names: Optional[List[str]] = None,
    ) -> str:
        """导出规则和模板到包文件

        Args:
            output_path: 输出文件路径
            include_templates: 是否包含模板
            include_styles: 是否包含学习记录
            rule_names: 只导出指定规则（None=全部）

        Returns:
            输出文件路径
        """
        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            # 导出规则
            if os.path.exists(self.rules_file):
                if rule_names:
                    # 只导出指定规则
                    content = self._filter_rules(rule_names)
                    with open(os.path.join(tmpdir, 'agent_rules.md'), 'w', encoding='utf-8') as f:
                        f.write(content)
                else:
                    shutil.copy2(self.rules_file, os.path.join(tmpdir, 'agent_rules.md'))

            # 导出模板
            if include_templates and os.path.exists(self.templates_dir):
                templates_tmp = os.path.join(tmpdir, 'templates')
                shutil.copytree(self.templates_dir, templates_tmp, dirs_exist_ok=True)

            # 导出学习记录
            if include_styles and os.path.exists(self.styles_file):
                shutil.copy2(self.styles_file, os.path.join(tmpdir, 'learned_styles.md'))

            # 创建元数据
            metadata = {
                'version': '1.0',
                'project_root': self.project_root,
                'exported_at': __import__('datetime').datetime.now().isoformat(),
                'includes': {
                    'rules': True,
                    'templates': include_templates,
                    'styles': include_styles,
                },
                'rule_count': self._count_rules(),
            }
            with open(os.path.join(tmpdir, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # 打包
            self._create_tarball(tmpdir, output_path)

        return output_path

    def import_rules(
        self,
        input_path: str,
        overwrite: bool = False,
        import_templates: bool = True,
        import_styles: bool = True,
    ) -> Dict:
        """从包文件导入规则和模板

        Args:
            input_path: 输入文件路径
            overwrite: 是否覆盖现有规则
            import_templates: 是否导入模板
            import_styles: 是否导入学习记录

        Returns:
            导入结果
        """
        result = {
            'rules_imported': 0,
            'templates_imported': 0,
            'styles_imported': False,
            'errors': [],
        }

        # 解压到临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                self._extract_tarball(input_path, tmpdir)
            except Exception as e:
                result['errors'].append(f'解压失败: {e}')
                return result

            # 读取元数据
            metadata_path = os.path.join(tmpdir, 'metadata.json')
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                print(f'导入包版本: {metadata.get("version", "未知")}')
                print(f'导出时间: {metadata.get("exported_at", "未知")}')

            # 导入规则
            rules_path = os.path.join(tmpdir, 'agent_rules.md')
            if os.path.exists(rules_path):
                result['rules_imported'] = self._import_rules_file(rules_path, overwrite)

            # 导入模板
            if import_templates:
                templates_path = os.path.join(tmpdir, 'templates')
                if os.path.exists(templates_path):
                    result['templates_imported'] = self._import_templates(templates_path)

            # 导入学习记录
            if import_styles:
                styles_path = os.path.join(tmpdir, 'learned_styles.md')
                if os.path.exists(styles_path):
                    result['styles_imported'] = self._import_styles(styles_path, overwrite)

        return result

    def _filter_rules(self, rule_names: List[str]) -> str:
        """过滤规则，只保留指定的规则"""
        if not os.path.exists(self.rules_file):
            return ''

        with open(self.rules_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析规则块
        import re

        blocks = re.split(r'^(## 规则：)', content, flags=re.MULTILINE)

        # 保留标题
        result = blocks[0]

        # 过滤规则
        for i in range(1, len(blocks), 2):
            if i + 1 < len(blocks):
                rule_header = blocks[i]
                rule_content = blocks[i + 1]
                rule_name = rule_header.replace('## 规则：', '').strip()

                if rule_name in rule_names:
                    result += rule_header + rule_content

        return result

    def _count_rules(self) -> int:
        """统计规则数量"""
        if not os.path.exists(self.rules_file):
            return 0

        with open(self.rules_file, 'r', encoding='utf-8') as f:
            content = f.read()

        import re

        return len(re.findall(r'^## 规则：', content, re.MULTILINE))

    def _create_tarball(self, source_dir: str, output_path: str):
        """创建 tar.gz 包"""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with tarfile.open(output_path, 'w:gz') as tar:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    tar.add(file_path, arcname=arcname)

    def _extract_tarball(self, input_path: str, target_dir: str):
        """解压 tar.gz 包"""
        with tarfile.open(input_path, 'r:gz') as tar:
            tar.extractall(target_dir)

    def _import_rules_file(self, rules_path: str, overwrite: bool) -> int:
        """导入规则文件"""
        with open(rules_path, 'r', encoding='utf-8') as f:
            new_content = f.read()

        import re

        new_rules = re.findall(r'^## 规则：(.+)$', new_content, re.MULTILINE)

        if overwrite:
            # 覆盖现有规则
            shutil.copy2(rules_path, self.rules_file)
            return len(new_rules)
        else:
            # 追加新规则（跳过已存在的）
            if os.path.exists(self.rules_file):
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
                existing_rules = set(re.findall(r'^## 规则：(.+)$', existing_content, re.MULTILINE))
            else:
                existing_content = ''
                existing_rules = set()

            # 只追加新规则
            imported = 0
            for rule_name in new_rules:
                if rule_name not in existing_rules:
                    # 提取规则内容
                    pattern = rf'^## 规则：{re.escape(rule_name)}$.*?(?=^## 规则：|\Z)'
                    match = re.search(pattern, new_content, re.MULTILINE | re.DOTALL)
                    if match:
                        rule_content = match.group(0)
                        with open(self.rules_file, 'a', encoding='utf-8') as f:
                            f.write('\n\n' + rule_content)
                        imported += 1

            return imported

    def _import_templates(self, templates_path: str) -> int:
        """导入模板"""
        imported = 0
        os.makedirs(self.templates_dir, exist_ok=True)

        for root, dirs, files in os.walk(templates_path):
            for file in files:
                if file.endswith('.py'):
                    src = os.path.join(root, file)
                    rel_path = os.path.relpath(src, templates_path)
                    dst = os.path.join(self.templates_dir, rel_path)

                    # 创建子目录
                    os.makedirs(os.path.dirname(dst), exist_ok=True)

                    # 复制文件
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        imported += 1

        return imported

    def _import_styles(self, styles_path: str, overwrite: bool) -> bool:
        """导入学习记录"""
        if overwrite or not os.path.exists(self.styles_file):
            shutil.copy2(styles_path, self.styles_file)
            return True
        else:
            # 追加
            with open(styles_path, 'r', encoding='utf-8') as f:
                new_content = f.read()
            with open(self.styles_file, 'a', encoding='utf-8') as f:
                f.write('\n\n' + new_content)
            return True

    def list_export_packages(self, directory: str = '.') -> List[Dict]:
        """列出目录下的导出包"""
        packages = []
        for file in os.listdir(directory):
            if file.endswith('.tar.gz'):
                path = os.path.join(directory, file)
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        self._extract_tarball(path, tmpdir)
                        metadata_path = os.path.join(tmpdir, 'metadata.json')
                        if os.path.exists(metadata_path):
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            packages.append(
                                {
                                    'file': file,
                                    'path': path,
                                    'metadata': metadata,
                                }
                            )
                        else:
                            packages.append(
                                {
                                    'file': file,
                                    'path': path,
                                    'metadata': {},
                                }
                            )
                except Exception:
                    pass

        return packages


def export_project_rules(output_path: str = 'agent_rules_export.tar.gz', **kwargs) -> str:
    """导出项目规则"""
    migrator = ProjectMigrator()
    return migrator.export_rules(output_path, **kwargs)


def import_project_rules(input_path: str, **kwargs) -> Dict:
    """导入项目规则"""
    migrator = ProjectMigrator()
    return migrator.import_rules(input_path, **kwargs)
