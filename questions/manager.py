#!/usr/bin/env python3
"""
408题库管理工具
基于SQLite和Tkinter的可视化题库管理系统
"""

import re
import json
import sqlite3
import shutil
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from pathlib import Path
from PIL import Image, ImageTk

# 科目配置
SUBJECTS = {
    "DS": {
        "name": "数据结构",
        "chapters": {
            "01": "基本概念",
            "02": "线性表",
            "03": "栈、队列和数组",
            "04": "树与二叉树",
            "05": "图",
            "06": "查找",
            "07": "排序",
        }
    },
    "CO": {
        "name": "计算机组成原理",
        "chapters": {
            "01": "计算机系统概述",
            "02": "数据的表示和运算",
            "03": "存储器层次结构",
            "04": "指令系统",
            "05": "中央处理器",
            "06": "总线和输入输出系统",
        }
    },
    "OS": {
        "name": "操作系统",
        "chapters": {
            "01": "操作系统概述",
            "02": "进程管理",
            "03": "内存管理",
            "04": "文件管理",
            "05": "输入输出管理",
        }
    },
    "CN": {
        "name": "计算机网络",
        "chapters": {
            "01": "计算机网络体系结构",
            "02": "物理层",
            "03": "数据链路层",
            "04": "网络层",
            "05": "传输层",
            "06": "应用层",
        }
    }
}

QUESTION_TYPES = {
    "single_choice": "单选题",
    "application": "应用题",
}

STATUS_TYPES = {
    "draft": "草稿",
    "published": "已发布",
    "deprecated": "已废弃"
}


class DatabaseManager:
    """数据库管理类"""

    def __init__(self, db_path="questions.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建题目表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                subject_code TEXT NOT NULL,
                chapter_num TEXT NOT NULL,
                question_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                question_text TEXT NOT NULL,
                option_a TEXT,
                option_b TEXT,
                option_c TEXT,
                option_d TEXT,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                knowledge TEXT,
                notes TEXT,
                created_date TEXT NOT NULL,
                last_modified TEXT NOT NULL,
                image_path TEXT
            )
        ''')

        # 创建科目表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')

        # 创建章节表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                subject_code TEXT,
                chapter_num TEXT,
                name TEXT NOT NULL,
                PRIMARY KEY (subject_code, chapter_num),
                FOREIGN KEY (subject_code) REFERENCES subjects(code)
            )
        ''')

        # 插入初始数据
        self._insert_initial_data(cursor)

        conn.commit()
        conn.close()

    def _insert_initial_data(self, cursor):
        """插入初始的科目和章节数据"""
        # 插入科目
        for code, info in SUBJECTS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO subjects (code, name) VALUES (?, ?)",
                (code, info["name"])
            )

        # 插入章节
        for subject_code, subject_info in SUBJECTS.items():
            for chapter_num, chapter_name in subject_info["chapters"].items():
                cursor.execute(
                    "INSERT OR IGNORE INTO chapters (subject_code, chapter_num, name) VALUES (?, ?, ?)",
                    (subject_code, chapter_num, chapter_name)
                )

    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)

    def execute_query(self, query, params=()):
        """执行查询并返回结果"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        conn.close()
        return result

    def execute_update(self, query, params=()):
        """执行更新操作"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()


class QuestionManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("408题库管理系统")
        self.root.geometry("1000x600")

        # 初始化数据库
        self.db = DatabaseManager()

        # 设置图标和样式
        self.setup_styles()

        # 当前选中的题目
        self.current_question_id = None
        self.current_question_data = None
        self.current_image_path = None
        self.image_label = None

        # 创建主界面
        self.create_main_interface()

        # 加载题目列表
        self.refresh_question_list()

    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TLabel", background="#f0f0f0")
        style.configure("Title.TLabel", font=("Arial", 12, "bold"))

    def create_main_interface(self):
        """创建主界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧：题目列表和搜索
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 右侧：题目编辑和详情
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH,
                         expand=True, padx=(10, 0))

        # 构建左侧界面
        self.create_left_panel(left_frame)

        # 构建右侧界面
        self.create_right_panel(right_frame)

    def create_left_panel(self, parent):
        """创建左侧面板：题目列表和搜索"""
        # 搜索框架
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<KeyRelease>', self.on_search)

        # 筛选框架
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="科目:").pack(side=tk.LEFT)
        self.filter_subject_var = tk.StringVar(value="all")
        subject_combo = ttk.Combobox(filter_frame, textvariable=self.filter_subject_var,
                                     values=[
                                         "全部"] + [f"{code} - {info['name']}" for code, info in SUBJECTS.items()],
                                     state="readonly", width=15)
        subject_combo.pack(side=tk.LEFT, padx=5)
        subject_combo.bind('<<ComboboxSelected>>', self.on_filter_change)

        ttk.Label(filter_frame, text="题型:").pack(side=tk.LEFT, padx=(10, 0))
        self.filter_type_var = tk.StringVar(value="all")
        type_combo = ttk.Combobox(filter_frame, textvariable=self.filter_type_var,
                                  values=["全部"] +
                                  list(QUESTION_TYPES.values()),
                                  state="readonly", width=12)
        type_combo.pack(side=tk.LEFT, padx=5)
        type_combo.bind('<<ComboboxSelected>>', self.on_filter_change)

        # 按钮框架
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(button_frame, text="刷新", command=self.refresh_question_list).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="新建题目", command=self.create_new_question_dialog).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导入题目", command=self.import_questions).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="导出题目", command=self.export_questions).pack(
            side=tk.LEFT, padx=5)

        # 题目列表
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # 创建树形视图显示题目列表
        columns = ("id", "subject", "chapter", "type", "status", "preview")
        self.tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=20)

        # 定义列
        self.tree.heading("id", text="题目ID")
        self.tree.heading("subject", text="科目")
        self.tree.heading("chapter", text="章节")
        self.tree.heading("type", text="题型")
        self.tree.heading("status", text="状态")
        self.tree.heading("preview", text="题目预览")

        self.tree.column("id", width=120)
        self.tree.column("subject", width=100)
        self.tree.column("chapter", width=100)
        self.tree.column("type", width=80)
        self.tree.column("status", width=60)
        self.tree.column("preview", width=300)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定双击事件
        self.tree.bind("<Double-1>", self.on_tree_double_click)

    def create_right_panel(self, parent):
        """创建右侧面板：题目编辑和详情"""
        # 创建选项卡
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 查看选项卡
        self.view_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.view_frame, text="查看题目")

        # 编辑选项卡
        self.edit_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.edit_frame, text="编辑题目")

        # 统计选项卡
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text="统计信息")

        # 构建查看界面
        self.create_view_tab(self.view_frame)

        # 构建编辑界面
        self.create_edit_tab(self.edit_frame)

        # 构建统计界面
        self.create_stats_tab(self.stats_frame)

    def create_view_tab(self, parent):
        """创建查看题目选项卡"""
        # 使用文本框显示题目内容
        self.view_text = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, width=80, height=30)
        self.view_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.view_text.config(state=tk.DISABLED)  # 初始状态为只读

    def create_edit_tab(self, parent):
        """创建编辑题目选项卡"""
        # 创建滚动框架
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(
            parent, orient=tk.VERTICAL, command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            if event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)      # Windows, macOS
        canvas.bind("<Button-4>", _on_mousewheel)        # Linux 上滚
        canvas.bind("<Button-5>", _on_mousewheel)        # Linux 下滚

        self.scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
        self.scrollable_frame.bind("<Button-4>", _on_mousewheel)
        self.scrollable_frame.bind("<Button-5>", _on_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 按钮
        button_frame = ttk.Frame(self.scrollable_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=(10, 10))
        ttk.Button(button_frame, text="保存题目", command=self.save_current_question).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="重置", command=self.reset_edit_form).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="删除题目",
                   command=self.delete_current_question).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="复制题目", command=self.duplicate_question).pack(
            side=tk.LEFT, padx=5)

        # 题目ID显示（不可编辑）
        id_frame = ttk.Frame(self.scrollable_frame)
        id_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(id_frame, text="题目ID:").pack(side=tk.LEFT)
        self.id_var = tk.StringVar()
        self.id_entry = ttk.Entry(
            id_frame, textvariable=self.id_var, state="readonly", width=20)
        self.id_entry.pack(side=tk.LEFT, padx=5)

        # 状态选择
        status_frame = ttk.Frame(self.scrollable_frame)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(status_frame, text="状态:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="draft")
        for status_code, status_name in STATUS_TYPES.items():
            ttk.Radiobutton(status_frame, text=status_name, variable=self.status_var,
                            value=status_code).pack(side=tk.LEFT, padx=5)

        # 题型选择
        type_frame = ttk.Frame(self.scrollable_frame)
        type_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(type_frame, text="题型:").pack(side=tk.LEFT)
        self.type_var = tk.StringVar(value="single_choice")
        type_combo = ttk.Combobox(type_frame, textvariable=self.type_var,
                                  values=list(QUESTION_TYPES.values()), state="readonly")
        type_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 题面编辑
        text_frame = ttk.Frame(self.scrollable_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        ttk.Label(text_frame, text="题面:").pack(anchor=tk.W)
        self.question_text = scrolledtext.ScrolledText(
            text_frame, wrap=tk.WORD, height=6)
        self.question_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # 图片上传区域
        image_frame = ttk.LabelFrame(self.scrollable_frame, text="题目附图")
        image_frame.pack(fill=tk.X, padx=10, pady=5)
        image_button_frame = ttk.Frame(image_frame)
        image_button_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(image_button_frame, text="上传图片",
                   command=self.upload_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(image_button_frame, text="删除图片",
                   command=self.delete_image).pack(side=tk.LEFT, padx=5)
        # 图片预览区域
        self.image_preview_frame = ttk.Frame(image_frame)
        self.image_preview_frame.pack(fill=tk.X, padx=5, pady=5)
        self.image_path_var = tk.StringVar()
        ttk.Label(self.image_preview_frame, textvariable=self.image_path_var,
                  foreground="blue").pack(anchor=tk.W)

        # 选项编辑（单选题）
        self.options_frame = ttk.LabelFrame(self.scrollable_frame, text="选项")
        self.options_frame.pack(fill=tk.X, padx=10, pady=5)
        self.option_vars = {}
        option_letters = ["A", "B", "C", "D"]
        for letter in option_letters:
            option_frame = ttk.Frame(self.options_frame)
            option_frame.pack(fill=tk.X, padx=5, pady=2)
            ttk.Label(option_frame, text=f"{letter}:").pack(side=tk.LEFT)
            var = tk.StringVar()
            entry = ttk.Entry(option_frame, textvariable=var)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            self.option_vars[letter] = var

        # 参考答案
        answer_frame = ttk.Frame(self.scrollable_frame)
        answer_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(answer_frame, text="参考答案:").pack(side=tk.LEFT)
        self.answer_var = tk.StringVar()
        self.answer_entry = ttk.Entry(
            answer_frame, textvariable=self.answer_var, width=30)
        self.answer_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 解析
        ttk.Label(self.scrollable_frame, text="解析:").pack(
            anchor=tk.W, padx=10, pady=(10, 0))
        self.explanation_text = scrolledtext.ScrolledText(
            self.scrollable_frame, wrap=tk.WORD, height=6)
        self.explanation_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 相关知识技巧
        ttk.Label(self.scrollable_frame, text="相关知识技巧:").pack(
            anchor=tk.W, padx=10, pady=(10, 0))
        self.knowledge_text = scrolledtext.ScrolledText(
            self.scrollable_frame, wrap=tk.WORD, height=4)
        self.knowledge_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 备注
        ttk.Label(self.scrollable_frame, text="备注:").pack(
            anchor=tk.W, padx=10, pady=(10, 0))
        self.notes_text = scrolledtext.ScrolledText(
            self.scrollable_frame, wrap=tk.WORD, height=3)
        self.notes_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def create_stats_tab(self, parent):
        """创建统计信息选项卡"""
        self.stats_text = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, width=80, height=30)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.stats_text.config(state=tk.DISABLED)

    def refresh_stats_tab(self):
        """刷新统计信息选项卡"""
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)

        # 获取统计信息
        stats = self.get_statistics()

        # 显示统计信息
        self.stats_text.insert(tk.END, "=== 题库统计信息 ===\n\n")
        self.stats_text.insert(tk.END, f"总题目数: {stats['total_questions']}\n\n")

        for subject, subject_stats in stats['subjects'].items():
            self.stats_text.insert(tk.END, f"【{subject}】\n")
            self.stats_text.insert(
                tk.END, f"  题目数: {subject_stats['total']}\n")
            for qtype, count in subject_stats['types'].items():
                self.stats_text.insert(tk.END, f"  {qtype}: {count}\n")
            self.stats_text.insert(tk.END, "\n")

        self.stats_text.config(state=tk.DISABLED)

    def get_statistics(self):
        """获取统计信息"""
        # 总题目数
        total = self.db.execute_query("SELECT COUNT(*) FROM questions")[0][0]

        stats = {
            'total_questions': total,
            'subjects': {}
        }

        # 各科目统计
        for subject_code, subject_info in SUBJECTS.items():
            subject_name = subject_info['name']
            subject_stats = self.db.execute_query('''
                SELECT 
                    COUNT(*) as total,
                    question_type,
                    COUNT(*) as type_count
                FROM questions 
                WHERE subject_code = ?
                GROUP BY question_type
            ''', (subject_code,))

            type_counts = {}
            total_subject = 0

            for row in subject_stats:
                type_name = QUESTION_TYPES.get(row[1], row[1])
                type_counts[type_name] = row[2]
                total_subject += row[2]

            stats['subjects'][subject_name] = {
                'total': total_subject,
                'types': type_counts
            }

        return stats

    def refresh_question_list(self, search_term=None, subject_filter=None, type_filter=None):
        """刷新题目列表"""
        # 清空现有列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 构建查询条件
        conditions = []
        params = []

        if search_term and search_term.strip():
            conditions.append(
                "(question_text LIKE ? OR id LIKE ? OR correct_answer LIKE ?)")
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        if subject_filter and subject_filter != "all":
            subject_code = subject_filter.split(" - ")[0]
            conditions.append("subject_code = ?")
            params.append(subject_code)

        if type_filter and type_filter != "all":
            # 找到题型代码
            type_code = None
            for code, name in QUESTION_TYPES.items():
                if name == type_filter:
                    type_code = code
                    break
            if type_code:
                conditions.append("question_type = ?")
                params.append(type_code)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 查询题目
        query = f'''
            SELECT 
                q.id, q.subject_code, q.chapter_num, q.question_type, q.status, 
                q.question_text,
                s.name as subject_name,
                c.name as chapter_name
            FROM questions q
            LEFT JOIN subjects s ON q.subject_code = s.code
            LEFT JOIN chapters c ON q.subject_code = c.subject_code AND q.chapter_num = c.chapter_num
            WHERE {where_clause}
            ORDER BY q.id
        '''

        questions = self.db.execute_query(query, params)

        # 添加到树形视图
        for q in questions:
            question_id, subject_code, chapter_num, q_type, status, question_text, subject_name, chapter_name = q

            # 提取题面前50个字符作为预览
            preview = question_text[:80] + \
                "..." if len(question_text) > 80 else question_text

            self.tree.insert("", tk.END, values=(
                question_id,
                subject_name,
                chapter_name,
                QUESTION_TYPES.get(q_type, q_type),
                STATUS_TYPES.get(status, status),
                preview
            ))

        # 同时刷新统计信息
        self.refresh_stats_tab()

    def on_search(self, event):
        """搜索框内容变化时的处理"""
        search_term = self.search_var.get()
        subject_filter = self.filter_subject_var.get(
        ) if self.filter_subject_var.get() != "全部" else None
        type_filter = self.filter_type_var.get(
        ) if self.filter_type_var.get() != "全部" else None
        self.refresh_question_list(search_term, subject_filter, type_filter)

    def on_filter_change(self, event):
        """筛选条件变化时的处理"""
        self.on_search(None)

    def on_tree_double_click(self, event):
        """树形视图双击事件"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            question_id = self.tree.item(item, "values")[0]
            self.load_question(question_id)

    def load_question(self, question_id):
        """加载题目到查看和编辑界面"""
        self.current_question_id = question_id

        # 从数据库查询题目
        query = '''
            SELECT * FROM questions WHERE id = ?
        '''
        result = self.db.execute_query(query, (question_id,))

        if not result:
            messagebox.showerror("错误", f"未找到题目 {question_id}")
            return

        # 解析结果
        row = result[0]
        question_data = {
            'id': row[0],
            'subject_code': row[1],
            'chapter_num': row[2],
            'question_type': row[3],
            'status': row[4],
            'question_text': row[5],
            'option_a': row[6],
            'option_b': row[7],
            'option_c': row[8],
            'option_d': row[9],
            'correct_answer': row[10],
            'explanation': row[11],
            'knowledge': row[12],
            'notes': row[13],
            'created_date': row[14],
            'last_modified': row[15],
            'image_path': row[16]
        }

        # 保存当前题目数据
        self.current_question_data = question_data

        # 更新查看界面
        self.update_view_tab(question_data)

        # 更新编辑界面
        self.update_edit_tab(question_data)

        # 切换到查看选项卡
        self.notebook.select(0)

    def update_view_tab(self, question_data):
        """更新查看选项卡内容"""
        self.view_text.config(state=tk.NORMAL)
        self.view_text.delete(1.0, tk.END)

        # 构建显示内容
        display_text = f"题目ID: {question_data['id']}\n"
        display_text += f"科目: {SUBJECTS[question_data['subject_code']]['name']}\n"
        display_text += f"章节: {SUBJECTS[question_data['subject_code']]['chapters'][question_data['chapter_num']]}\n"
        display_text += f"题型: {QUESTION_TYPES.get(question_data['question_type'], question_data['question_type'])}\n"
        display_text += f"状态: {STATUS_TYPES.get(question_data['status'], question_data['status'])}\n"
        display_text += f"创建日期: {question_data['created_date']}\n"
        display_text += f"修改日期: {question_data['last_modified']}\n"

        # 显示图片信息
        if question_data['image_path']:
            display_text += f"附图: {question_data['image_path']}\n"

        display_text += "\n" + "="*50 + "\n\n"
        display_text += f"{question_data['question_text']}\n\n"

        # 如果是单选题，显示选项
        if question_data['question_type'] == 'single_choice':
            options = []
            for letter in ['A', 'B', 'C', 'D']:
                option_value = question_data.get(f'option_{letter.lower()}')
                if option_value:
                    options.append(f"{letter}. {option_value}")

            if options:
                display_text += "选项:\n" + "\n".join(options) + "\n\n"

        display_text += f"参考答案: {question_data['correct_answer']}\n\n"

        if question_data['explanation']:
            display_text += "解析:\n" + question_data['explanation'] + "\n\n"

        if question_data['knowledge']:
            display_text += "相关知识技巧:\n" + question_data['knowledge'] + "\n\n"

        if question_data['notes']:
            display_text += "备注:\n" + question_data['notes'] + "\n"

        self.view_text.insert(1.0, display_text)
        self.view_text.config(state=tk.DISABLED)

    def update_edit_tab(self, question_data):
        """更新编辑选项卡内容"""
        # 更新基本信息
        self.id_var.set(question_data['id'])
        self.status_var.set(question_data['status'])
        self.type_var.set(QUESTION_TYPES.get(
            question_data['question_type'], question_data['question_type']))

        # 题面
        self.question_text.delete(1.0, tk.END)
        self.question_text.insert(1.0, question_data['question_text'])

        # 更新图片信息
        self.current_image_path = question_data.get('image_path')
        if self.current_image_path:
            self.image_path_var.set(f"当前图片: {self.current_image_path}")
        else:
            self.image_path_var.set("未上传图片")

        # 如果是单选题，显示选项
        if question_data['question_type'] == 'single_choice':
            for letter in ['A', 'B', 'C', 'D']:
                var = self.option_vars[letter]
                var.set(question_data.get(f'option_{letter.lower()}', ''))
            self.options_frame.pack(fill=tk.X, padx=10, pady=5)
        else:
            # 应用题不需要选项，隐藏选项框架
            self.options_frame.pack_forget()

        # 参考答案
        self.answer_var.set(question_data['correct_answer'])

        # 解析
        self.explanation_text.delete(1.0, tk.END)
        self.explanation_text.insert(1.0, question_data['explanation'] or '')

        # 相关知识技巧
        self.knowledge_text.delete(1.0, tk.END)
        self.knowledge_text.insert(1.0, question_data['knowledge'] or '')

        # 备注
        self.notes_text.delete(1.0, tk.END)
        self.notes_text.insert(1.0, question_data['notes'] or '')

    def upload_image(self):
        """上传图片"""
        if not self.current_question_id:
            messagebox.showwarning("警告", "请先选择或创建一个题目")
            return

        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.gif *.bmp"),
                       ("所有文件", "*.*")]
        )

        if not file_path:
            return

        # 创建图片目录
        image_dir = Path("assets/images")
        image_dir.mkdir(parents=True, exist_ok=True)

        # 生成新的图片文件名
        file_extension = Path(file_path).suffix
        new_image_name = f"{self.current_question_id}{file_extension}"
        new_image_path = image_dir / new_image_name

        try:
            # 复制图片到目标目录
            shutil.copy2(file_path, new_image_path)

            # 更新数据库
            self.db.execute_update(
                "UPDATE questions SET image_path = ? WHERE id = ?",
                (str(new_image_path), self.current_question_id)
            )

            # 更新界面
            self.current_image_path = str(new_image_path)
            self.image_path_var.set(f"当前图片: {new_image_name}")

            messagebox.showinfo("成功", "图片上传成功!")

        except Exception as e:
            messagebox.showerror("错误", f"图片上传失败: {e}")

    def delete_image(self):
        """删除图片"""
        if not self.current_question_id or not self.current_image_path:
            messagebox.showwarning("警告", "当前题目没有图片")
            return

        result = messagebox.askyesno("确认删除", "确定要删除这张图片吗？")
        if not result:
            return

        try:
            # 删除图片文件
            if Path(self.current_image_path).exists():
                Path(self.current_image_path).unlink()

            # 更新数据库
            self.db.execute_update(
                "UPDATE questions SET image_path = NULL WHERE id = ?",
                (self.current_question_id,)
            )

            # 更新界面
            self.current_image_path = None
            self.image_path_var.set("未上传图片")

            messagebox.showinfo("成功", "图片删除成功!")

        except Exception as e:
            messagebox.showerror("错误", f"图片删除失败: {e}")

    def create_new_question_dialog(self):
        """创建新题目对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("创建新题目")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()

        # 科目选择
        subject_frame = ttk.Frame(dialog)
        subject_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(subject_frame, text="科目:").pack(side=tk.LEFT)
        self.new_subject_var = tk.StringVar()
        subject_combo = ttk.Combobox(subject_frame, textvariable=self.new_subject_var,
                                     values=[
                                         f"{code} - {info['name']}" for code, info in SUBJECTS.items()],
                                     state="readonly")
        subject_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 章节选择
        chapter_frame = ttk.Frame(dialog)
        chapter_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(chapter_frame, text="章节:").pack(side=tk.LEFT)
        self.new_chapter_var = tk.StringVar()
        self.chapter_combo = ttk.Combobox(
            chapter_frame, textvariable=self.new_chapter_var, state="readonly")
        self.chapter_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 绑定科目变化事件
        subject_combo.bind('<<ComboboxSelected>>', self.on_subject_selected)

        # 题型选择 - 只保留单选题和应用题
        type_frame = ttk.Frame(dialog)
        type_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(type_frame, text="题型:").pack(side=tk.LEFT)
        self.new_type_var = tk.StringVar(value="单选题")
        new_type_combo = ttk.Combobox(type_frame, textvariable=self.new_type_var,
                                      values=list(QUESTION_TYPES.values()), state="readonly")
        new_type_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 按钮框架
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=20)

        ttk.Button(button_frame, text="创建", command=lambda: self.create_question_from_dialog(
            dialog)).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(
            side=tk.RIGHT, padx=5)

    def on_subject_selected(self, event):
        """科目选择变化时更新章节选项"""
        subject_str = self.new_subject_var.get()
        if subject_str:
            subject_code = subject_str.split(" - ")[0]
            chapters = SUBJECTS[subject_code]["chapters"]
            chapter_values = [f"{num} - {name}" for num,
                              name in chapters.items()]
            self.chapter_combo['values'] = chapter_values
            if chapter_values:
                self.chapter_combo.set(chapter_values[0])

    def create_question_from_dialog(self, dialog):
        """从对话框创建新题目"""
        subject_str = self.new_subject_var.get()
        chapter_str = self.new_chapter_var.get()
        question_type_str = self.new_type_var.get()

        if not subject_str or not chapter_str:
            messagebox.showerror("错误", "请选择科目和章节")
            return

        # 解析科目和章节
        subject_code = subject_str.split(" - ")[0]
        chapter_num = chapter_str.split(" - ")[0]

        # 查找题型代码
        question_type_code = None
        for code, name in QUESTION_TYPES.items():
            if name == question_type_str:
                question_type_code = code
                break

        if not question_type_code:
            messagebox.showerror("错误", "无效的题型")
            return

        # 生成题目ID
        question_id = self.generate_question_id(subject_code, chapter_num)

        # 创建题目数据
        current_time = datetime.now().strftime("%Y-%m-%d")
        question_data = {
            "id": question_id,
            "subject_code": subject_code,
            "chapter_num": chapter_num,
            "question_type": question_type_code,
            "status": "draft",
            "question_text": "请输入题面内容",
            "option_a": "",
            "option_b": "",
            "option_c": "",
            "option_d": "",
            "correct_answer": "",
            "explanation": "",
            "knowledge": "",
            "notes": "",
            "created_date": current_time,
            "last_modified": current_time,
            "image_path": None
        }

        # 保存题目到数据库
        self.insert_question(question_data)

        # 刷新列表并加载新题目
        self.refresh_question_list()
        self.load_question(question_id)

        # 关闭对话框
        dialog.destroy()

        messagebox.showinfo("成功", f"题目 {question_id} 创建成功!")

    def generate_question_id(self, subject_code: str, chapter_num: str) -> str:
        """生成新的题目ID"""
        # 查询该章节下已有的最大序号
        query = '''
            SELECT id FROM questions 
            WHERE subject_code = ? AND chapter_num = ?
            ORDER BY id DESC LIMIT 1
        '''
        result = self.db.execute_query(query, (subject_code, chapter_num))

        if result:
            # 提取已有文件的最大序号
            last_id = result[0][0]
            match = re.match(rf"{subject_code}{chapter_num}(\d{{6}})", last_id)
            if match:
                last_num = int(match.group(1))
                new_num = last_num + 1
            else:
                new_num = 1
        else:
            new_num = 1

        return f"{subject_code}{chapter_num}{new_num:06d}"

    def insert_question(self, question_data):
        """插入新题目到数据库"""
        query = '''
            INSERT INTO questions (
                id, subject_code, chapter_num, question_type, status, question_text,
                option_a, option_b, option_c, option_d, correct_answer,
                explanation, knowledge, notes, created_date, last_modified, image_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        params = (
            question_data['id'], question_data['subject_code'], question_data['chapter_num'],
            question_data['question_type'], question_data['status'], question_data['question_text'],
            question_data['option_a'], question_data['option_b'], question_data['option_c'],
            question_data['option_d'], question_data['correct_answer'],
            question_data['explanation'], question_data['knowledge'], question_data['notes'],
            question_data['created_date'], question_data['last_modified'], question_data['image_path']
        )

        self.db.execute_update(query, params)

    def update_question(self, question_data):
        """更新题目到数据库"""
        query = '''
            UPDATE questions SET
                subject_code = ?, chapter_num = ?, question_type = ?, status = ?, question_text = ?,
                option_a = ?, option_b = ?, option_c = ?, option_d = ?, correct_answer = ?,
                explanation = ?, knowledge = ?, notes = ?, last_modified = ?, image_path = ?
            WHERE id = ?
        '''

        params = (
            question_data['subject_code'], question_data['chapter_num'], question_data['question_type'],
            question_data['status'], question_data['question_text'], question_data['option_a'],
            question_data['option_b'], question_data['option_c'], question_data['option_d'],
            question_data['correct_answer'], question_data['explanation'],
            question_data['knowledge'], question_data['notes'], datetime.now().strftime(
                "%Y-%m-%d"),
            question_data['image_path'], question_data['id']
        )

        self.db.execute_update(query, params)

    def save_current_question(self):
        """保存当前编辑的题目"""
        if not self.current_question_id:
            messagebox.showwarning("警告", "没有选中任何题目")
            return

        # 收集编辑界面的数据
        question_text = self.question_text.get(1.0, tk.END).strip()

        # 如果是单选题，收集选项
        options = {}
        if self.get_question_type_code() == 'single_choice':
            for letter, var in self.option_vars.items():
                option_text = var.get().strip()
                options[letter] = option_text

        correct_answer = self.answer_var.get().strip()
        explanation = self.explanation_text.get(1.0, tk.END).strip()
        knowledge = self.knowledge_text.get(1.0, tk.END).strip()
        notes = self.notes_text.get(1.0, tk.END).strip()

        # 验证必要字段
        if not question_text:
            messagebox.showerror("错误", "题面内容不能为空")
            return

        # 构建题目数据
        question_data = {
            "id": self.current_question_id,
            "subject_code": self.current_question_data["subject_code"],
            "chapter_num": self.current_question_data["chapter_num"],
            "question_type": self.get_question_type_code(),
            "status": self.status_var.get(),
            "question_text": question_text,
            "option_a": options.get("A", ""),
            "option_b": options.get("B", ""),
            "option_c": options.get("C", ""),
            "option_d": options.get("D", ""),
            "correct_answer": correct_answer,
            "explanation": explanation,
            "knowledge": knowledge,
            "notes": notes,
            "created_date": self.current_question_data["created_date"],
            "image_path": self.current_image_path
        }

        # 更新题目
        self.update_question(question_data)

        # 刷新列表
        self.refresh_question_list()

    def get_question_type_code(self):
        """获取当前选择的题型代码"""
        type_name = self.type_var.get()
        for code, name in QUESTION_TYPES.items():
            if name == type_name:
                return code
        return "single_choice"

    def reset_edit_form(self):
        """重置编辑表单"""
        if self.current_question_id:
            self.load_question(self.current_question_id)
        else:
            # 清空表单
            self.id_var.set("")
            self.status_var.set("draft")
            self.type_var.set("单选题")
            self.question_text.delete(1.0, tk.END)
            for var in self.option_vars.values():
                var.set("")
            self.answer_var.set("")
            self.explanation_text.delete(1.0, tk.END)
            self.knowledge_text.delete(1.0, tk.END)
            self.notes_text.delete(1.0, tk.END)
            self.image_path_var.set("未上传图片")
            self.current_image_path = None

    def delete_current_question(self):
        """删除当前题目"""
        if not self.current_question_id:
            messagebox.showwarning("警告", "没有选中任何题目")
            return

        result = messagebox.askyesno(
            "确认删除", f"确定要删除题目 {self.current_question_id} 吗？")
        if result:
            try:
                # 删除关联的图片文件
                if self.current_image_path and Path(self.current_image_path).exists():
                    Path(self.current_image_path).unlink()

                # 从数据库删除题目
                self.db.execute_update(
                    "DELETE FROM questions WHERE id = ?", (self.current_question_id,))
                self.current_question_id = None
                self.current_question_data = None
                self.current_image_path = None
                self.reset_edit_form()
                self.refresh_question_list()
                messagebox.showinfo("成功", "题目删除成功!")
            except Exception as e:
                messagebox.showerror("错误", f"删除题目失败: {e}")

    def duplicate_question(self):
        """复制当前题目"""
        if not self.current_question_id:
            messagebox.showwarning("警告", "没有选中任何题目")
            return

        # 生成新的题目ID
        subject_code = self.current_question_data["subject_code"]
        chapter_num = self.current_question_data["chapter_num"]
        new_question_id = self.generate_question_id(subject_code, chapter_num)

        # 复制题目数据
        new_question_data = self.current_question_data.copy()
        new_question_data["id"] = new_question_id
        new_question_data["created_date"] = datetime.now().strftime("%Y-%m-%d")
        new_question_data["last_modified"] = datetime.now().strftime(
            "%Y-%m-%d")
        new_question_data["status"] = "draft"

        # 复制图片文件（如果存在）
        if self.current_image_path and Path(self.current_image_path).exists():
            file_extension = Path(self.current_image_path).suffix
            new_image_path = Path("assets/images") / \
                f"{new_question_id}{file_extension}"
            shutil.copy2(self.current_image_path, new_image_path)
            new_question_data["image_path"] = str(new_image_path)

        # 插入新题目
        self.insert_question(new_question_data)

        # 刷新列表并加载新题目
        self.refresh_question_list()
        self.load_question(new_question_id)

        messagebox.showinfo("成功", f"题目复制成功! 新题目ID: {new_question_id}")

    def import_questions(self):
        """从文件导入题目（支持覆盖已有题目）"""
        file_path = filedialog.askopenfilename(
            title="选择导入文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                questions_data = json.load(f)
            imported_count = 0
            updated_count = 0
            for q_data in questions_data:
                q_id = q_data.get('id')
                if not q_id:
                    continue  # 跳过无ID的题目
                # 检查是否已存在
                existing = self.db.execute_query(
                    "SELECT id FROM questions WHERE id = ?", (q_id,))
                if existing:
                    # 更新已有题目
                    self.update_question(q_data)
                    updated_count += 1
                else:
                    # 插入新题目
                    self.insert_question(q_data)
                    imported_count += 1
            self.refresh_question_list()
            messagebox.showinfo(
                "成功", f"导入完成：新增 {imported_count} 道，覆盖 {updated_count} 道题目。")
        except Exception as e:
            messagebox.showerror("错误", f"导入题目失败: {e}")

    def export_questions(self):
        """导出题目到文件"""
        file_path = filedialog.asksaveasfilename(
            title="保存导出文件",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )

        if not file_path:
            return

        try:
            # 获取所有题目
            questions = self.db.execute_query("SELECT * FROM questions")

            # 构建导出数据
            export_data = []
            for row in questions:
                question_dict = {
                    'id': row[0],
                    'subject_code': row[1],
                    'chapter_num': row[2],
                    'question_type': row[3],
                    'status': row[4],
                    'question_text': row[5],
                    'option_a': row[6],
                    'option_b': row[7],
                    'option_c': row[8],
                    'option_d': row[9],
                    'correct_answer': row[10],
                    'explanation': row[11],
                    'knowledge': row[12],
                    'notes': row[13],
                    'created_date': row[14],
                    'last_modified': row[15],
                    'image_path': row[16]
                }
                export_data.append(question_dict)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            messagebox.showinfo("成功", f"成功导出 {len(export_data)} 道题目")

        except Exception as e:
            messagebox.showerror("错误", f"导出题目失败: {e}")


def main():
    """主函数"""
    root = tk.Tk()
    app = QuestionManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
