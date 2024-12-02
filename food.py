import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import threading
import time


class DietTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("营养追踪程序")

        # 设置窗口大小和位置
        window_width = 800
        window_height = 700
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = int(screen_width / 2 - window_width / 2)
        center_y = int(screen_height / 2 - window_height / 2)
        self.root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')

        # 初始化数据库
        self.conn = sqlite3.connect('diet_records.db')
        self.cursor = self.conn.cursor()

        # 创建表（如果不存在）
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                food TEXT,
                carbs REAL,
                protein REAL,
                fat REAL
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_weight (
                date TEXT PRIMARY KEY,
                weight REAL
            )
        ''')
        self.conn.commit()

        # 检查是否是新的一天，如果是则清空数据
        self.check_and_clear_old_data()

        # 记录当前日期
        self.current_date = datetime.now().strftime('%Y-%m-%d')

        # 创建界面
        self.create_widgets()

        # 启动日期检查线程
        self.stop_thread = False
        self.date_check_thread = threading.Thread(target=self.check_date, daemon=True)
        self.date_check_thread.start()

        # 加载今日数据
        self.load_data()

        # 绑定关闭窗口事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 日期显示
        self.date_label = ttk.Label(main_frame, text=f"当前日期: {self.current_date}", font=('Arial', 12, 'bold'))
        self.date_label.pack(pady=5)

        # 体重输入区域
        weight_frame = ttk.LabelFrame(main_frame, text="设置每日目标", padding="10")
        weight_frame.pack(fill="x", pady=10)

        ttk.Label(weight_frame, text="体重(kg):", font=('Arial', 10)).pack(side="left", padx=5)
        self.weight_entry = ttk.Entry(weight_frame, width=10)
        self.weight_entry.pack(side="left", padx=5)
        ttk.Button(weight_frame, text="设置体重", command=self.calculate_targets).pack(side="left", padx=5)

        # 目标显示
        self.target_label = ttk.Label(weight_frame, text="请输入体重", font=('Arial', 10))
        self.target_label.pack(side="left", padx=5)

        # 食物输入区域
        input_frame = ttk.LabelFrame(main_frame, text="添加食物记录", padding="10")
        input_frame.pack(fill="x", pady=10)

        labels = ['食物:', '碳水(g):', '蛋白质(g):', '脂肪(g):']
        self.entries = {}
        for label in labels:
            ttk.Label(input_frame, text=label, font=('Arial', 10)).pack(side="left", padx=2)
            self.entries[label] = ttk.Entry(input_frame, width=10)
            self.entries[label].pack(side="left", padx=2)

        ttk.Button(input_frame, text="添加记录", command=self.add_food).pack(side="left", padx=5)

        # 进度显示区域
        progress_frame = ttk.LabelFrame(main_frame, text="营养素进度", padding="10")
        progress_frame.pack(fill="x", pady=10)

        # 碳水进度
        carbs_frame = ttk.Frame(progress_frame)
        carbs_frame.pack(fill="x", pady=5)
        ttk.Label(carbs_frame, text="碳水:", font=('Arial', 10)).pack(side="left", padx=5)
        self.carbs_progress = ttk.Progressbar(carbs_frame, length=300, mode='determinate')
        self.carbs_progress.pack(side="left", padx=5)
        self.carbs_label = ttk.Label(carbs_frame, text="0/0g", font=('Arial', 10))
        self.carbs_label.pack(side="left", padx=5)
        self.carbs_remaining = ttk.Label(carbs_frame, text="剩余: 0g", font=('Arial', 10))
        self.carbs_remaining.pack(side="left", padx=5)

        # 蛋白质进度
        protein_frame = ttk.Frame(progress_frame)
        protein_frame.pack(fill="x", pady=5)
        ttk.Label(protein_frame, text="蛋白质:", font=('Arial', 10)).pack(side="left", padx=5)
        self.protein_progress = ttk.Progressbar(protein_frame, length=300, mode='determinate')
        self.protein_progress.pack(side="left", padx=5)
        self.protein_label = ttk.Label(protein_frame, text="0/0g", font=('Arial', 10))
        self.protein_label.pack(side="left", padx=5)
        self.protein_remaining = ttk.Label(protein_frame, text="剩余: 0g", font=('Arial', 10))
        self.protein_remaining.pack(side="left", padx=5)

        # 脂肪进度
        fat_frame = ttk.Frame(progress_frame)
        fat_frame.pack(fill="x", pady=5)
        ttk.Label(fat_frame, text="脂肪:", font=('Arial', 10)).pack(side="left", padx=5)
        self.fat_progress = ttk.Progressbar(fat_frame, length=300, mode='determinate')
        self.fat_progress.pack(side="left", padx=5)
        self.fat_label = ttk.Label(fat_frame, text="0/0g", font=('Arial', 10))
        self.fat_label.pack(side="left", padx=5)
        self.fat_remaining = ttk.Label(fat_frame, text="剩余: 0g", font=('Arial', 10))
        self.fat_remaining.pack(side="left", padx=5)

        # 食物记录表格
        table_frame = ttk.LabelFrame(main_frame, text="今日饮食记录", padding="10")
        table_frame.pack(fill="both", expand=True, pady=10)

        # 创建表格和滚动条
        tree_scroll = ttk.Scrollbar(table_frame)
        tree_scroll.pack(side="right", fill="y")

        self.tree = ttk.Treeview(table_frame, columns=('id', '食物', '碳水', '蛋白质', '脂肪', '热量'),
                                 show='headings', height=8, yscrollcommand=tree_scroll.set)
        tree_scroll.config(command=self.tree.yview)

        # 设置列
        self.tree.column('id', width=0, stretch=False)  # 隐藏ID列
        self.tree.heading('id', text='ID')

        column_widths = {'食物': 200, '碳水': 100, '蛋白质': 100, '脂肪': 100, '热量': 100}
        for col, width in column_widths.items():
            self.tree.column(col, width=width, anchor='center')
            self.tree.heading(col, text=col)

        self.tree.pack(fill="both", expand=True)

        # 删除按钮
        ttk.Button(main_frame, text="删除选中记录", command=self.delete_selected).pack(pady=5)

        # 总计显示
        self.summary_label = ttk.Label(main_frame, text="", font=('Arial', 10, 'bold'))
        self.summary_label.pack(pady=5)

    def update_progress_bars(self, totals):
        """更新进度条和标签"""
        if hasattr(self, 'carbs_target'):
            # 更新碳水进度
            carbs_percent = min(100, (totals['carbs'] / self.carbs_target * 100))
            self.carbs_progress['value'] = carbs_percent
            self.carbs_label.config(text=f"{totals['carbs']:.1f}/{self.carbs_target:.1f}g")
            remaining_carbs = max(0, self.carbs_target - totals['carbs'])
            self.carbs_remaining.config(text=f"剩余: {remaining_carbs:.1f}g")

            # 更新蛋白质进度
            protein_percent = min(100, (totals['protein'] / self.protein_target * 100))
            self.protein_progress['value'] = protein_percent
            self.protein_label.config(text=f"{totals['protein']:.1f}/{self.protein_target:.1f}g")
            remaining_protein = max(0, self.protein_target - totals['protein'])
            self.protein_remaining.config(text=f"剩余: {remaining_protein:.1f}g")

            # 更新脂肪进度
            fat_percent = min(100, (totals['fat'] / self.fat_target * 100))
            self.fat_progress['value'] = fat_percent
            self.fat_label.config(text=f"{totals['fat']:.1f}/{self.fat_target:.1f}g")
            remaining_fat = max(0, self.fat_target - totals['fat'])
            self.fat_remaining.config(text=f"剩余: {remaining_fat:.1f}g")

    def calculate_targets(self):
        """计算每日营养目标"""
        try:
            weight = self.validate_number(self.weight_entry.get())
            if weight == 0:
                raise ValueError("体重不能为0")

            self.carbs_target = weight * 2  # 碳水 = 体重 * 2
            self.protein_target = weight * 1.5  # 蛋白质 = 体重 * 1.5
            self.fat_target = 40  # 固定40g脂肪

            # 保存体重记录
            self.cursor.execute('''
                INSERT OR REPLACE INTO daily_weight (date, weight)
                VALUES (?, ?)
            ''', (self.current_date, weight))
            self.conn.commit()

            target_text = f"目标 - 碳水: {self.carbs_target:.1f}g  蛋白质: {self.protein_target:.1f}g  脂肪: {self.fat_target:.1f}g"
            self.target_label.config(text=target_text)
            self.load_data()
        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def load_data(self):
        """加载和显示数据"""
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 加载今日数据
        self.cursor.execute('SELECT id, food, carbs, protein, fat FROM meals WHERE date = ?', (self.current_date,))

        total = {'carbs': 0, 'protein': 0, 'fat': 0}
        for row in self.cursor.fetchall():
            id_, food, carbs, protein, fat = row
            calories = carbs * 4 + protein * 4 + fat * 9
            self.tree.insert('', 'end', values=(id_, food, carbs, protein, fat, f"{calories:.1f}"))

            total['carbs'] += carbs
            total['protein'] += protein
            total['fat'] += fat

        # 更新总计
        total_cals = total['carbs'] * 4 + total['protein'] * 4 + total['fat'] * 9
        summary = f"总计 - 碳水: {total['carbs']:.1f}g  蛋白质: {total['protein']:.1f}g  "
        summary += f"脂肪: {total['fat']:.1f}g  热量: {total_cals:.1f}kcal"
        self.summary_label.config(text=summary)

        # 更新进度条
        self.update_progress_bars(total)

    def check_and_clear_old_data(self):
        """检查并清空旧数据"""
        today = datetime.now().strftime('%Y-%m-%d')

        # 删除非今天的数据
        self.cursor.execute('DELETE FROM meals WHERE date != ?', (today,))
        self.cursor.execute('DELETE FROM daily_weight WHERE date != ?', (today,))
        self.conn.commit()

    def validate_number(self, value):
        """验证并转换数值输入"""
        try:
            if not value.strip():  # 如果输入为空，返回0
                return 0.0
            num = float(value)
            if num < 0:
                raise ValueError("数值不能为负")
            return num
        except ValueError:
            raise ValueError(f"'{value}' 不是有效的数值，请输入数字")

    def delete_selected(self):
        """删除选中的记录"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("提示", "请先选择要删除的记录")
            return

        if messagebox.askyesno("确认", "确定要删除选中的记录吗？"):
            for item in selected_items:
                # 获取记录ID
                record_id = self.tree.item(item)['values'][0]
                # 从数据库删除
                self.cursor.execute('DELETE FROM meals WHERE id = ?', (record_id,))

            self.conn.commit()
            self.load_data()

    def add_food(self):
        """添加食物记录"""
        try:
            food = self.entries['食物:'].get().strip()
            if not food:
                messagebox.showerror("错误", "请输入食物名称")
                return

            # 获取并验证数值输入
            carbs = self.validate_number(self.entries['碳水(g):'].get())
            protein = self.validate_number(self.entries['蛋白质(g):'].get())
            fat = self.validate_number(self.entries['脂肪(g):'].get())

            self.cursor.execute('''
                INSERT INTO meals (date, food, carbs, protein, fat)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.current_date, food, carbs, protein, fat))
            self.conn.commit()

            # 清空输入框
            for entry in self.entries.values():
                entry.delete(0, tk.END)

            self.load_data()

        except ValueError as e:
            messagebox.showerror("错误", str(e))

    def check_date(self):
        """检查日期变化的线程函数"""
        while not self.stop_thread:
            current_time = datetime.now()
            new_date = current_time.strftime('%Y-%m-%d')

            if new_date != self.current_date:
                self.current_date = new_date
                self.root.after(0, self.handle_date_change)

            time.sleep(60)

    def handle_date_change(self):
        """处理日期变化"""
        self.date_label.config(text=f"当前日期: {self.current_date}")

        # 清空旧数据
        self.check_and_clear_old_data()

        # 重置进度条和标签
        if hasattr(self, 'carbs_progress'):
            self.carbs_progress['value'] = 0
            self.protein_progress['value'] = 0
            self.fat_progress['value'] = 0
            self.carbs_label.config(text="0/0g")
            self.protein_label.config(text="0/0g")
            self.fat_label.config(text="0/0g")
            self.carbs_remaining.config(text="剩余: 0g")
            self.protein_remaining.config(text="剩余: 0g")
            self.fat_remaining.config(text="剩余: 0g")

        # 重置其他界面元素
        self.target_label.config(text="请输入体重")
        self.weight_entry.delete(0, tk.END)
        self.summary_label.config(text="")
        self.load_data()

    def on_closing(self):
            # 在这里处理窗口关闭事件
            # 例如，询问用户是否确认关闭，保存数据等
        if messagebox.askokcancel("退出", "你确定要退出吗？"):
                self.root.destroy()
        # 提醒用户
        messagebox.showinfo("提示", "记得明天也要来哦！")
    # [其余方法保持不变...]


if __name__ == '__main__':
    root = tk.Tk()
    app = DietTracker(root)
    root.mainloop()