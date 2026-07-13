import os
import re
import traceback

class RenameEngine:
    """基于官方 22 字段全信托结论的重命名引擎"""
    def __init__(self, rename_format, movie_format, folder_format, movie_folder_format, season_format, regex_rules=None):
        self.rename_format = rename_format
        self.movie_format = movie_format
        self.folder_format = folder_format
        self.movie_folder_format = movie_folder_format
        self.season_format = season_format
        self.regex_rules = regex_rules or []

    def apply_regex_rules(self, text):
        for pattern_str, replacement in self.regex_rules:
            try:
                flags = 0
                if pattern_str.startswith('(?i)') or pattern_str.startswith('(?I)'):
                    pattern_str, flags = pattern_str[4:], re.IGNORECASE
                text = re.sub(pattern_str, replacement, text, flags=flags)
            except re.error: continue
        return text

    def build_paths(self, old_path, rec_result, custom_settings=None):
        old_filename = os.path.basename(old_path)
        old_dir = os.path.dirname(old_path)
        file_no_ext, ext = os.path.splitext(old_filename)

        # 1. 获取全量 22 字段
        format_data = rec_result.to_dict().copy()
        is_movie = (format_data.get('category') == "电影")
        
        # 2. 补全/修正辅助字段 (s_val, e_val 用于补零逻辑)
        s_val = format_data.get('season', 1)
        e_val = format_data.get('episode', '1')
        
        # 3. 处理自定义覆盖逻辑
        if custom_settings:
            if custom_settings.get('tmdb_id_override'):
                format_data['tmdb_id'] = custom_settings['tmdb_id_override']
            if custom_settings.get('custom_season_enabled'):
                s_val = custom_settings['custom_season_value']
            if custom_settings.get('custom_episode_offset_enabled'):
                try:
                    offset = int(custom_settings.get('custom_episode_offset_value', 0))
                    original_ep = int(re.search(r'\d+', str(e_val)).group()) if re.search(r'\d+', str(e_val)) else 1
                    e_val = str(max(1, original_ep + offset))
                except: pass

        # --- 后缀剥离工具 ---
        def safe_strip(val):
            if not val: return ""
            return os.path.splitext(str(val))[0]

        # 4. 重新映射占位符字典 (严格遵循官方要求)
        final_placeholders = {
            'title': format_data.get('title', ''),
            'tmdb_id': format_data.get('tmdb_id', ''),
            'category': format_data.get('category', ''),
            'processed_name': safe_strip(format_data.get('processed_name', '')), # 渲染后标题 (剥离后缀)
            'poster_path': format_data.get('poster_path', ''),
            'release_date': format_data.get('release_date', ''),
            'season': str(s_val),
            'season_02': str(s_val).zfill(2),
            'episode': str(e_val),
            'episode_02': str(e_val).zfill(2),
            'team': format_data.get('team', ''),
            'resolution': format_data.get('resolution', ''),
            'video_encode': format_data.get('video_encode', ''),
            'video_effect': format_data.get('video_effect', ''),
            'audio_encode': format_data.get('audio_encode', ''),
            'subtitle': format_data.get('subtitle', ''),
            'source': format_data.get('source', ''),
            'platform': format_data.get('platform', ''),
            'origin_country': format_data.get('origin_country', ''),
            'vote_average': format_data.get('vote_average', 0.0),
            'year': format_data.get('year', ''),
            'duration': format_data.get('duration', ''),
            'filename': safe_strip(format_data.get('filename', file_no_ext)), # 原始名 (剥离后缀)
            'path': format_data.get('path', old_path)
        }

        # 5. 生成结果
        file_template = self.movie_format if is_movie else self.rename_format
        folder_template = self.movie_folder_format if is_movie else self.folder_format
        
        # 文件名
        new_filename = file_template
        for k, v in final_placeholders.items():
            new_filename = new_filename.replace(f'{{{k}}}', str(v))
        new_filename = self.apply_regex_rules(new_filename)
        new_filename = re.sub(r'[<>:"/\\|?*]', '_', new_filename).strip(" .")

        # 主文件夹
        main_folder = folder_template
        for k, v in final_placeholders.items():
            main_folder = main_folder.replace(f'{{{k}}}', str(v))
        main_folder = re.sub(r'[<>:"/\\|?*]', '_', main_folder).strip(" .")

        # 季文件夹
        season_folder = ""
        if not is_movie or (custom_settings and custom_settings.get('custom_season_enabled')):
            if self.season_format.strip():
                season_folder = self.season_format
                for k, v in final_placeholders.items():
                    season_folder = season_folder.replace(f'{{{k}}}', str(v))
                season_folder = re.sub(r'[<>:"/\\|?*]', '_', season_folder).strip(" .")

        target_dir = os.path.join(old_dir, main_folder, season_folder) if season_folder else os.path.join(old_dir, main_folder)
        return os.path.join(target_dir, f"{new_filename}{ext}"), main_folder, season_folder

    def execute_rename(self, old_path, new_path):
        if os.path.normpath(old_path) == os.path.normpath(new_path): return True, "无需重命名"
        if os.path.exists(new_path): return False, f"目标已存在: {new_path}"
        try:
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            os.rename(old_path, new_path)
            return True, "成功"
        except Exception as e: return False, str(e)
