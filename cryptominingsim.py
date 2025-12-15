import customtkinter as ctk
import json
import time
import random
import os
import threading
from datetime import datetime

# --- RICH LIBRARY ---
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich.align import Align

SAVE_FILE = "save_game.json"

# ==========================================
# PHẦN 1: BACKEND (Logic Kinh Tế & Game)
# ==========================================
class GameBackend:
    def __init__(self):
        self.wallet = 1000.0 # Cho vốn khởi nghiệp tí để trả tiền điện
        self.click_power = 1.0
        
        # Cấu hình Algo (Reward Mult càng cao càng nhiều tiền)
        self.algorithms = {
            "SHA-256": {"name": "SHA-256 (BTC)", "difficulty": 1.0, "reward_mult": 1.0},
            "Ethash":  {"name": "Ethash (ETH)",   "difficulty": 0.8, "reward_mult": 0.75},
            "Scrypt":  {"name": "Scrypt (LTC)",   "difficulty": 0.5, "reward_mult": 0.45},
            "Kawpow":  {"name": "Kawpow (RVN)",   "difficulty": 0.6, "reward_mult": 0.6}, # New
            "RandomX": {"name": "RandomX (XMR)",  "difficulty": 0.3, "reward_mult": 0.3}, # New
        }
        self.current_algo = "SHA-256"
        self.current_block_progress = 0.0
        self.last_diff_update = time.time()
        self.last_auto_switch = time.time()
        
        # Chỉ số kinh tế
        self.electricity_cost_kwh = 0.12  # $0.12 per kWh
        self.internet_fee_per_sec = 0.05  # Phí mạng
        self.maintenance_rate = 0.15      # 15% giá trị máy
        self.maintenance_cycle = 3600     # 15% mỗi 1 giờ chơi (3600s)
        
        # DANH SÁCH MÁY ĐÀO (Thêm 10 loại mới siêu cấp)
        self.upgrades = {
            # --- TIER 1: STARTER ---
            "gpu_1": {"name": "GTX 1660 Super", "cost": 150, "rate": 30.0, "watts": 125, "count": 0, "type": "GPU"},
            "gpu_2": {"name": "RTX 3060 Ti",    "cost": 450, "rate": 60.0, "watts": 200, "count": 0, "type": "GPU"},
            "gpu_3": {"name": "RTX 4090",       "cost": 1600, "rate": 150.0, "watts": 450, "count": 0, "type": "GPU"},
            
            # --- TIER 2: ADVANCED (New GPU) ---
            "gpu_4": {"name": "RTX 5090 Ti Prototype", "cost": 3500, "rate": 350.0, "watts": 600, "count": 0, "type": "GPU"},
            "gpu_5": {"name": "NVIDIA H100 Cluster",   "cost": 30000, "rate": 2500.0, "watts": 700, "count": 0, "type": "GPU"},
            "gpu_6": {"name": "Quantum GPU Core",      "cost": 85000, "rate": 8000.0, "watts": 1200, "count": 0, "type": "GPU"},

            # --- TIER 3: ASIC MINERS ---
            "asic_1": {"name": "Antminer S19",   "cost": 2500, "rate": 1100.0, "watts": 3250, "count": 0, "type": "ASIC"},
            "asic_2": {"name": "Antminer S21 Hydro", "cost": 6500, "rate": 3500.0, "watts": 5000, "count": 0, "type": "ASIC"},
            
            # --- TIER 4: INDUSTRIAL ASIC (New) ---
            "asic_3": {"name": "WhatsMiner M60S++", "cost": 15000, "rate": 9000.0, "watts": 6500, "count": 0, "type": "ASIC"},
            "asic_4": {"name": "Bitmain E9 Pro Max", "cost": 45000, "rate": 28000.0, "watts": 8000, "count": 0, "type": "ASIC"},
            "asic_5": {"name": "Mars Rover Miner",   "cost": 120000, "rate": 85000.0, "watts": 12000, "count": 0, "type": "ASIC"},
            "asic_6": {"name": "Dyson Sphere Node",  "cost": 500000, "rate": 400000.0, "watts": 50000, "count": 0, "type": "ASIC"},

            # --- TIER 5: ENDGAME PRO (New) ---
            "pro_1": {"name": "Mining Container",   "cost": 150000, "rate": 120000.0, "watts": 25000, "count": 0, "type": "PRO"},
            "pro_2": {"name": "Geothermal Plant",   "cost": 1200000, "rate": 1000000.0, "watts": 150000, "count": 0, "type": "PRO"},
            "pro_3": {"name": "Fusion Reactor Rig", "cost": 5000000, "rate": 4500000.0, "watts": 400000, "count": 0, "type": "PRO"},
            "pro_4": {"name": "Alien AI Core",      "cost": 99999999, "rate": 99000000.0, "watts": 1000000, "count": 0, "type": "PRO"},
        }

        self.load_game()

    # --- TÍNH TOÁN ---
    def get_total_hashrate(self):
        return sum(item["rate"] * item["count"] for item in self.upgrades.values())

    def get_total_watts(self):
        return sum(item["watts"] * item["count"] for item in self.upgrades.values())
    
    def get_total_inventory_value(self):
        # Giá trị gốc để tính bảo trì
        return sum(item["cost"] * item["count"] for item in self.upgrades.values())

    def auto_switch_algo(self):
        """Logic Smart Switch: Chọn Algo có tỷ lệ Reward/Difficulty cao nhất"""
        best_algo = self.current_algo
        best_ratio = -1
        
        for name, data in self.algorithms.items():
            # Tỉ lệ càng cao càng ngon (Nhiều thưởng / Khó thấp)
            ratio = data["reward_mult"] / data["difficulty"]
            if ratio > best_ratio:
                best_ratio = ratio
                best_algo = name
        
        if best_algo != self.current_algo:
            old = self.current_algo
            self.current_algo = best_algo
            self.current_block_progress = 0 # Reset progress khi đổi mạng
            return True, f"Auto-Switch: {old} -> {best_algo} (Better Profit!)"
        return False, None

    def mine_tick(self, auto_mode=False):
        # 1. Update Algo Diff Dynamic
        if time.time() - self.last_diff_update > 300: # 5 phút
            for k in self.algorithms:
                self.algorithms[k]["difficulty"] *= random.uniform(0.95, 1.1)
            self.last_diff_update = time.time()

        # 2. Auto Switch Logic (Chỉ chạy ở AFK Mode hoặc mỗi 60s)
        switch_msg = None
        if auto_mode and time.time() - self.last_auto_switch > 60:
            switched, msg = self.auto_switch_algo()
            if switched: switch_msg = msg
            self.last_auto_switch = time.time()

        # 3. Tính toán cơ bản
        algo = self.algorithms[self.current_algo]
        total_hashrate = self.get_total_hashrate()
        block_req = 1000 * algo["difficulty"]
        
        # 4. Tính CHI PHÍ (Expenses)
        # - Điện: (Watts / 1000) * (Price/kWh) / 3600 (để ra per second)
        total_watts = self.get_total_watts()
        elec_cost = (total_watts / 1000) * self.electricity_cost_kwh / 3600
        
        # - Bảo trì: (Tổng giá trị * 15%) / 3600 (giả sử chu kỳ 1h)
        inventory_val = self.get_total_inventory_value()
        maint_cost = (inventory_val * self.maintenance_rate) / self.maintenance_cycle
        
        # - Tổng chi phí giây này
        total_expense = elec_cost + self.internet_fee_per_sec + maint_cost

        # 5. Đào coin
        self.current_block_progress += total_hashrate
        blocks_mined = 0
        revenue = 0.0
        base_reward = 10 * algo["reward_mult"]

        while self.current_block_progress >= block_req:
            self.current_block_progress -= block_req
            revenue += base_reward
            blocks_mined += 1

        # 6. Cập nhật ví (Có thể âm nếu lỗ vốn!)
        profit = revenue - total_expense
        self.wallet += profit

        return {
            "wallet": self.wallet,
            "progress": self.current_block_progress,
            "req": block_req,
            "blocks": blocks_mined,
            "revenue": revenue,
            "expense": total_expense,
            "switch_msg": switch_msg
        }

    def manual_mine(self):
        self.current_block_progress += self.click_power * 500
        return self.wallet

    def buy_upgrade(self, key):
        item = self.upgrades.get(key)
        if item and self.wallet >= item["cost"]:
            self.wallet -= item["cost"]
            item["count"] += 1
            item["cost"] = int(item["cost"] * 1.15) # Lạm phát 15%
            self.save_game()
            return True, f"Mua {item['name']} thành công!"
        return False, "Không đủ tiền hoặc đang nợ!"

    def save_game(self):
        data = {
            "wallet": self.wallet,
            "upgrades": self.upgrades,
            "current_algo": self.current_algo,
            "algorithms": self.algorithms
        }
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f)
            
    def load_game(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    data = json.load(f)
                    self.wallet = data.get("wallet", 1000)
                    self.current_algo = data.get("current_algo", "SHA-256")
                    
                    saved_upgrades = data.get("upgrades", {})
                    for k, v in saved_upgrades.items():
                        if k in self.upgrades: self.upgrades[k] = v
            except: pass

# ==========================================
# PHẦN 2: AFK MODE (RICH DASHBOARD)
# ==========================================
def run_afk_mode(backend):
    console = Console()
    console.clear()

    def make_layout():
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=8)
        )
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        layout["left"].split_column(
            Layout(name="stats", ratio=1),
            Layout(name="financial", ratio=1)
        )
        return layout

    def get_header():
        title = f"🚀 ULTRA MINER AUTOMATION | Algo: [bold cyan]{backend.current_algo}[/]"
        return Panel(Align.center(title), style="bold white on blue")

    def get_stats_panel(data):
        table = Table(expand=True, show_header=False, box=None)
        
        hr = backend.get_total_hashrate()
        diff = backend.algorithms[backend.current_algo]["difficulty"]
        
        table.add_row("⚡ Hashrate", f"[bold green]{hr:,.0f} H/s[/]")
        table.add_row("🧱 Difficulty", f"{diff:.2f}")
        table.add_row("📊 Block Prog", f"{data['progress']:.0f} / {data['req']:.0f}")
        
        return Panel(table, title="Mining Stats", border_style="green")

    def get_financial_panel(data):
        table = Table(expand=True, show_header=False, box=None)
        
        rev = data['revenue'] * 10 # Ước lượng doanh thu x10 tick rate
        exp = data['expense'] * 10
        net = rev - exp
        
        color = "green" if net >= 0 else "red"
        
        table.add_row("💰 Wallet", f"[bold gold1]${backend.wallet:,.2f}[/]")
        table.add_row("📈 Rev/sec", f"${rev:,.2f}")
        table.add_row("📉 Exp/sec", f"[red]-${exp:,.2f}[/]")
        table.add_row("💵 Net Profit", f"[{color}]${net:,.2f}/s[/]")
        table.add_row("🔌 Power", f"[yellow]{backend.get_total_watts():,.0f} W[/]")
        
        return Panel(table, title="Financials (Realtime)", border_style="yellow")

    def get_hardware_panel():
        table = Table(title="Active Rigs", expand=True, show_lines=False)
        table.add_column("Device", style="cyan")
        table.add_column("Qty", justify="right")
        table.add_column("Cost/Day", justify="right", style="red")

        # Tính chi phí bảo trì + điện ước tính cho mỗi loại
        for k, v in backend.upgrades.items():
            if v['count'] > 0:
                # Ước tính chi phí vận hành (để display cho vui)
                maint = (v['cost'] * 0.15 * v['count']) / 3600 
                elec = (v['watts'] * v['count'] / 1000) * 0.12 / 3600
                total_cost = (maint + elec) * 3600 * 24 # Per day
                
                table.add_row(v['name'], str(v['count']), f"-${total_cost:,.0f}")
        
        return Panel(table, title="Hardware Status", border_style="blue")

    # Loop
    layout = make_layout()
    log_msgs = ["[SYSTEM] AFK Mode Initialized. Smart Switching Active."]
    
    with Live(layout, refresh_per_second=10, screen=True) as live:
        while True:
            # Tick 10 lần/giây cho mượt, nhưng backend logic chia nhỏ
            # Ở đây mình gọi mine_tick liên tục
            data = backend.mine_tick(auto_mode=True)
            
            # Xử lý log
            if data['blocks'] > 0:
                log_msgs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Mined {data['blocks']} blocks. Rev: +${data['revenue']:.2f}")
            if data['switch_msg']:
                log_msgs.append(f"[bold magenta] >> {data['switch_msg']}[/]")
                
            if len(log_msgs) > 6: log_msgs.pop(0)
            
            # Update UI
            layout["header"].update(get_header())
            layout["left"]["stats"].update(get_stats_panel(data))
            layout["left"]["financial"].update(get_financial_panel(data))
            layout["right"].update(get_hardware_panel())
            layout["footer"].update(Panel("\n".join(log_msgs), title="System Log"))
            
            time.sleep(0.1)

# ==========================================
# PHẦN 3: GUI MODE (CUSTOMTKINTER)
# ==========================================
class GameGUI(ctk.CTk):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.title("RustMiner GUI - Management Console")
        self.geometry("1000x700")
        ctk.set_appearance_mode("Dark")
        
        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # LEFT SIDE
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.lbl_wallet = ctk.CTkLabel(self.left_frame, text="$0.00", font=("Arial", 32, "bold"), text_color="#2ecc71")
        self.lbl_wallet.pack(pady=20)
        
        self.lbl_stats = ctk.CTkLabel(self.left_frame, text="Hashrate: 0 H/s\nPower: 0 W", font=("Arial", 14))
        self.lbl_stats.pack(pady=10)

        # Expenses Info
        self.lbl_expenses = ctk.CTkLabel(self.left_frame, text="Expenses: $0/s", text_color="#e74c3c")
        self.lbl_expenses.pack(pady=5)

        self.btn_mine = ctk.CTkButton(self.left_frame, text="MANUAL MINE", height=60, fg_color="#f39c12", command=self.on_manual_mine)
        self.btn_mine.pack(pady=30, padx=20, fill="x")

        # RIGHT SIDE (SHOP)
        self.right_frame = ctk.CTkScrollableFrame(self, label_text="HARDWARE MARKET (With OpEx Analysis)")
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        self.refresh_shop()
        self.auto_loop()

    def refresh_shop(self):
        for w in self.right_frame.winfo_children(): w.destroy()
        
        # Nhóm item theo loại để dễ nhìn
        for key, item in self.backend.upgrades.items():
            card = ctk.CTkFrame(self.right_frame)
            card.pack(fill="x", pady=4, padx=5)
            
            # Màu sắc phân loại
            c = "#3498db" if item['type']=="GPU" else "#9b59b6" if item['type']=="ASIC" else "#e67e22"
            
            # Info
            info = f"{item['name']} (Lv {item['count']})\n+{item['rate']} H/s | ⚡ {item['watts']}W"
            ctk.CTkLabel(card, text=f"[{item['type']}]", text_color=c, width=40).pack(side="left")
            ctk.CTkLabel(card, text=info, anchor="w", justify="left").pack(side="left", padx=5)
            
            # Nút mua
            btn_text = f"${item['cost']}"
            ctk.CTkButton(card, text=btn_text, width=80, fg_color="#2c3e50", 
                          command=lambda k=key: self.buy(k)).pack(side="right", padx=10, pady=10)

    def buy(self, key):
        success, msg = self.backend.buy_upgrade(key)
        if success: self.refresh_shop()

    def on_manual_mine(self):
        self.backend.manual_mine()
        self.update_ui()

    def auto_loop(self):
        # Tick backend
        data = self.backend.mine_tick(auto_mode=False) # GUI không auto switch, để user tự chỉnh nếu thích
        
        # Update UI Labels
        self.lbl_wallet.configure(text=f"${self.backend.wallet:,.2f}")
        self.lbl_stats.configure(text=f"Hashrate: {self.backend.get_total_hashrate():,.0f} H/s\nPower: {self.backend.get_total_watts():,.0f} W")
        self.lbl_expenses.configure(text=f"OpEx: -${data['expense']:.2f}/s")
        
        self.after(1000, self.auto_loop) # 1 giây refresh 1 lần

    def update_ui(self):
        # Hàm phụ để update nhanh khi click
        self.lbl_wallet.configure(text=f"${self.backend.wallet:,.2f}")

# ==========================================
# MAIN LAUNCHER
# ==========================================
if __name__ == "__main__":
    backend = GameBackend()
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=== RUST-MINER SIMULATOR V4 (HARDCORE) ===")
    print("1. Start GUI (Quản lý, Mua sắm)")
    print("2. Start AFK Mode (Auto Switch Algo, Rich Dashboard)")
    
    c = input("Select mode: ").strip()
    
    if c == "2":
        try:
            run_afk_mode(backend)
        except KeyboardInterrupt:
            backend.save_game()
            print("Saved & Exited.")
    else:
        app = GameGUI(backend)
        app.mainloop()
