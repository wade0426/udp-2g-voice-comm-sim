import tkinter as tk
from tkinter import ttk, messagebox
import socket
from Final_Exam_Project_2G import main, apply_preset_config, get_local_ip

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind('<Enter>', self.enter)
        self.widget.bind('<Leave>', self.leave)

    def enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=self.text, justify='left',
                      background="#ffffe0", relief='solid', borderwidth=1,
                      font=("Arial", "9", "normal"), padx=5, pady=2)
        label.pack()

    def leave(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class AudioUI:
    def __init__(self, root):
        self.root = root
        self.root.title("模擬2G通訊系統")
        self.root.geometry("300x600")  # 增加窗口高度以容納更多組件
        
        # 創建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 預設配置部分
        ttk.Label(main_frame, text="配置設置", font=('Arial', 12, 'bold')).grid(row=0, column=0, pady=10)
        
        self.preset_var = tk.BooleanVar(value=True)
        ttk.Radiobutton(main_frame, text="使用預設配置", variable=self.preset_var, 
                       value=True, command=self.toggle_preset).grid(row=1, column=0)
        ttk.Radiobutton(main_frame, text="手動配置", variable=self.preset_var, 
                       value=False, command=self.toggle_preset).grid(row=1, column=1)
        
        # 預設配置選擇
        self.preset_frame = ttk.LabelFrame(main_frame, text="預設配置", padding="5")
        self.preset_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        self.preset_number = tk.StringVar(value="1")
        ttk.Radiobutton(self.preset_frame, text="預設 1 (高音質模式)", 
                       variable=self.preset_number, value="1").grid(row=0, column=0)
        ttk.Radiobutton(self.preset_frame, text="預設 2 (低音質 模式)", 
                       variable=self.preset_number, value="2").grid(row=0, column=1)
        
        # 添加預設配置說明
        preset_info = ttk.Label(self.preset_frame, text="(懸停查看詳細說明)")
        preset_info.grid(row=1, column=0, columnspan=2, pady=(2,0))
        ToolTip(preset_info, "預設 1 (高音質模式)：\n"
                            "- 16位元量化 (65536級)\n"
                            "- 較高截止頻率\n"
                            "- 較高濾波器階數\n"
                            "- 停用FSK和交錯處理\n"
                            "預設 2 (低音質模式)：\n"
                            "- 4位元量化 (16級)\n"
                            "- 較低截止頻率\n"
                            "- 較低濾波器階數\n"
                            "- 啟用FSK和交錯處理\n")
        
        # 手動配置框架
        self.manual_frame = ttk.LabelFrame(main_frame, text="手動配置", padding="5")
        self.manual_frame.grid(row=3, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        # 量化等級
        quant_frame = ttk.Frame(self.manual_frame)
        quant_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(quant_frame, text="量化等級:").grid(row=0, column=0, padx=5)
        self.quantization_var = tk.StringVar(value="256")
        quantization_combo = ttk.Combobox(quant_frame, textvariable=self.quantization_var, 
                                        values=["16", "256", "65536"], width=10)
        quantization_combo.grid(row=0, column=1, padx=5)
        
        quant_info = ttk.Label(quant_frame, text="(16=低音質, 256=中等, 65536=高音質)")
        quant_info.grid(row=1, column=0, columnspan=2, pady=(2,0))
        ToolTip(quant_info, "量化等級影響音質和數據量：\n"
                           "16 = 4位元量化：低音質，最小數據量\n"
                           "256 = 8位元量化：中等音質，推薦使用\n"
                           "65536 = 16位元量化：高音質，較大數據量")
        
        # 截止頻率
        freq_frame = ttk.Frame(self.manual_frame)
        freq_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(freq_frame, text="截止頻率 (Hz):").grid(row=0, column=0, padx=5)
        self.cutoff_var = tk.StringVar(value="4000")
        cutoff_entry = ttk.Entry(freq_frame, textvariable=self.cutoff_var, width=10)
        cutoff_entry.grid(row=0, column=1, padx=5)
        
        freq_info = ttk.Label(freq_frame, text="(建議範圍: 1000-8000 Hz)")
        freq_info.grid(row=1, column=0, columnspan=2, pady=(2,0))
        ToolTip(freq_info, "截止頻率影響音頻頻寬：\n"
                          "較低的值（如1000Hz）：減少噪音但可能失真\n"
                          "較高的值（如8000Hz）：保留更多細節但可能有噪音\n"
                          "建議值：3000-4000 Hz")
        
        # 濾波器階數
        filter_frame = ttk.Frame(self.manual_frame)
        filter_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Label(filter_frame, text="濾波器階數:").grid(row=0, column=0, padx=5)
        self.filter_order_var = tk.StringVar(value="4")
        filter_order_combo = ttk.Combobox(filter_frame, textvariable=self.filter_order_var,
                                        values=["2", "4", "6", "8"], width=10)
        filter_order_combo.grid(row=0, column=1, padx=5)
        
        filter_info = ttk.Label(filter_frame, text="(可選: 2, 4, 6, 8)")
        filter_info.grid(row=1, column=0, columnspan=2, pady=(2,0))
        ToolTip(filter_info, "濾波器階數影響濾波效果：\n"
                            "2-4階：較快的響應，較弱的濾波效果\n"
                            "6-8階：較強的濾波效果，但可能產生延遲\n"
                            "建議值：4或6階")

        # 加密設置
        self.encryption_var = tk.BooleanVar(value=False)
        encrypt_check = ttk.Checkbutton(self.manual_frame, text="啟用加密", 
                                      variable=self.encryption_var)
        encrypt_check.grid(row=3, column=0, columnspan=2, pady=5)
        ToolTip(encrypt_check, "使用XOR加密保護音頻數據\n"
                              "注意：兩端必須使用相同的加密設置")
        
        # FSK調變
        self.fsk_var = tk.BooleanVar(value=False)
        fsk_check = ttk.Checkbutton(self.manual_frame, text="啟用FSK調變", 
                                   variable=self.fsk_var)
        fsk_check.grid(row=4, column=0, columnspan=2, pady=5)
        ToolTip(fsk_check, "頻移鍵控調變\n"
                          "可以提高傳輸的抗干擾能力\n"
                          "注意：兩端必須使用相同的FSK設置")
        
        # 交錯處理
        self.interleaving_var = tk.BooleanVar(value=False)
        interleave_check = ttk.Checkbutton(self.manual_frame, text="啟用交錯處理", 
                                          variable=self.interleaving_var)
        interleave_check.grid(row=5, column=0, columnspan=2, pady=5)
        ToolTip(interleave_check, "數據交錯處理可以減少突發錯誤的影響\n"
                                 "注意：兩端必須使用相同的交錯設置")
        
        # 設備角色選擇
        role_frame = ttk.LabelFrame(main_frame, text="設備角色", padding="5")
        role_frame.grid(row=4, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        self.role_var = tk.StringVar(value="1")
        ttk.Radiobutton(role_frame, text="A設備 (端口5000)", 
                       variable=self.role_var, value="1").grid(row=0, column=0)
        ttk.Radiobutton(role_frame, text="B設備 (端口5001)", 
                       variable=self.role_var, value="2").grid(row=0, column=1)
        
        # IP地址顯示
        ip_frame = ttk.LabelFrame(main_frame, text="網絡信息", padding="5")
        ip_frame.grid(row=5, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        local_ip = get_local_ip()
        ttk.Label(ip_frame, text=f"本機IP: {local_ip}").grid(row=0, column=0)
        
        # 啟動按鈕
        ttk.Button(main_frame, text="啟動通訊", command=self.start_communication
                  ).grid(row=6, column=0, columnspan=2, pady=20)
        
        # 狀態標籤
        self.status_label = ttk.Label(main_frame, text="就緒", font=('Arial', 10))
        self.status_label.grid(row=7, column=0, columnspan=2)
        
        # 初始化界面狀態
        self.toggle_preset()

    def toggle_preset(self):
        """切換預設/手動配置的顯示狀態"""
        if self.preset_var.get():
            self.preset_frame.grid()
            self.manual_frame.grid_remove()
        else:
            self.preset_frame.grid_remove()
            self.manual_frame.grid()

    def apply_manual_config(self):
        """應用手動配置"""
        import Final_Exam_Project_2G as cfg
        try:
            cfg.QUANTIZATION_LEVELS = int(self.quantization_var.get())
            cfg.CUTOFF_FREQUENCY = int(self.cutoff_var.get())
            cfg.FILTER_ORDER = int(self.filter_order_var.get())
            cfg.USE_ENCRYPTION = self.encryption_var.get()
            cfg.USE_FSK = self.fsk_var.get()
            cfg.USE_INTERLEAVING = self.interleaving_var.get()
            
            print("\n=== 已套用手動配置 ===")
            print(f"量化等級: {cfg.QUANTIZATION_LEVELS}")
            print(f"截止頻率: {cfg.CUTOFF_FREQUENCY} Hz")
            print(f"濾波器階數: {cfg.FILTER_ORDER}")
            print(f"加密: {'啟用' if cfg.USE_ENCRYPTION else '停用'}")
            print(f"FSK調變: {'啟用' if cfg.USE_FSK else '停用'}")
            print(f"交錯處理: {'啟用' if cfg.USE_INTERLEAVING else '停用'}")
            print("=====================\n")
            return True
        except ValueError as e:
            messagebox.showerror("錯誤", f"配置值無效: {str(e)}")
            return False

    def start_communication(self):
        try:
            self.status_label.config(text="正在啟動通訊...")
            self.root.update()
            
            if self.preset_var.get():
                # 使用預設配置
                if not apply_preset_config(int(self.preset_number.get())):
                    raise Exception("預設配置應用失敗")
            else:
                # 使用手動配置
                if not self.apply_manual_config():
                    raise Exception("手動配置應用失敗")
            
            # 啟動主程序
            self.root.withdraw()  # 隱藏主窗口
            main(role=self.role_var.get())
            self.root.deiconify()  # 顯示主窗口
            
        except Exception as e:
            messagebox.showerror("錯誤", f"啟動失敗: {str(e)}")
            self.status_label.config(text="啟動失敗")
            self.root.deiconify()

def launch_ui():
    root = tk.Tk()
    app = AudioUI(root)
    root.mainloop()

if __name__ == "__main__":
    launch_ui()