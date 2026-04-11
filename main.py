"""
rukk filter工具 - PyWebview版本
使用 pywebview 作为GUI框架，实现RGB颜色滤镜、亮度滤镜和系统亮度控制功能
"""

import os
import sys
import ctypes
import json
import shutil
import time
import webview
from typing import Dict, List, Optional
import threading
from PIL import Image
import pystray
import win32event
import win32api
import psutil
import keyboard

# 调试模式标志，True时输出详细日志
DEBUG = False
# 应用程序图标路径
ICON = "logo.png"

# 单实例锁，用于防止程序重复启动
SINGLE_INSTANCE_LOCK = None
# 窗口可见性标志，控制主窗口显示/隐藏状态
WINDOW_VISIBLE = True

# 默认快捷键配置
DEFAULT_HOTKEYS = {
    "increaseIntensity": "Ctrl+Right",  # 增加滤镜强度
    "decreaseIntensity": "Ctrl+Left",  # 减少滤镜强度
    "increaseBrightness": "Alt+Right",  # 增加亮度
    "decreaseBrightness": "Alt+Left",  # 减少亮度
    "nextPreset": "Ctrl+Up",  # 下一个预设
    "prevPreset": "Ctrl+Down",  # 上一个预设
    "toggleFilter": "Ctrl+O",  # 切换滤镜开关
    "toggleWindow": "Alt+S",  # 切换窗口显示/隐藏
    "turnOffScreen": "Ctrl+Shift+S",  # 熄屏
}

# 默认预设配置列表
DEFAULT_PRESETS = [
    {
        "name": "默认",
        "rgb": [30, 32, 38],
        "intensity": 30,
        "brightnessFilter": 0,
        "systemBrightness": 0,
    },
    {
        "name": "暖色",
        "rgb": [255, 160, 80],
        "intensity": 50,
        "brightnessFilter": 0,
        "systemBrightness": 100,
    },
    {
        "name": "冷色",
        "rgb": [80, 140, 255],
        "intensity": 50,
        "brightnessFilter": 0,
        "systemBrightness": 100,
    },
    {
        "name": "夜间",
        "rgb": [255, 100, 50],
        "intensity": 50,
        "brightnessFilter": 0,
        "systemBrightness": 100,
    },
    {
        "name": "阅读",
        "rgb": [200, 220, 180],
        "intensity": 50,
        "brightnessFilter": 0,
        "systemBrightness": 100,
    },
    {
        "name": "护眼",
        "rgb": [255, 180, 120],
        "intensity": 50,
        "brightnessFilter": 0,
        "systemBrightness": 100,
    },
]

# 配置文件名称
CONFIG_FILE = "config.json"

# 当前快捷键配置（运行时从配置文件加载）
currentHotkeys = DEFAULT_HOTKEYS.copy()

# 已注册的全局快捷键列表（用于取消注册）
registeredHotkeys = []

# 滤镜开关状态
filterEnabled = True
# 背景图显示状态
showBackgroundImage = True
# 关闭按钮显示状态
showCloseButton = False
# 当前预设列表（运行时从配置文件加载）
currentPresets = None

# 配置缓存（内存中）
configCache = {}


def get_base_path():
    """获取基础路径（兼容开发环境和打包后的环境）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(filename):
    """获取资源文件的路径（打包后从临时目录获取）"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        return os.path.join(meipass, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def ensure_config_exists():
    """确保配置文件存在于exe目录（打包后从临时目录复制）"""
    config_path = os.path.join(get_base_path(), CONFIG_FILE)
    if getattr(sys, "frozen", False) and not os.path.exists(config_path):
        meipass = getattr(sys, "_MEIPASS", "")
        bundled_config = os.path.join(meipass, CONFIG_FILE)
        if os.path.exists(bundled_config):
            shutil.copy2(bundled_config, config_path)


def load_config():
    """从文件加载配置（包含快捷键和预设）"""
    global currentHotkeys, currentPresets, configCache
    ensure_config_exists()
    config_path = os.path.join(get_base_path(), CONFIG_FILE)
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                configCache = json.load(f)
            currentHotkeys = configCache.get("hotkeys", DEFAULT_HOTKEYS.copy())
            currentPresets = configCache.get(
                "presets", json.loads(json.dumps(DEFAULT_PRESETS))
            )
            global showBackgroundImage
            showBackgroundImage = configCache.get("showBackgroundImage", True)
            global showCloseButton
            showCloseButton = configCache.get("showCloseButton", True)
            print(f"配置已加载: {len(currentPresets)} 个预设")
        else:
            currentHotkeys = DEFAULT_HOTKEYS.copy()
            currentPresets = json.loads(json.dumps(DEFAULT_PRESETS))
            save_config()
    except Exception as e:
        print(f"加载配置失败: {e}")
        currentHotkeys = DEFAULT_HOTKEYS.copy()
        currentPresets = json.loads(json.dumps(DEFAULT_PRESETS))


def save_config():
    """保存配置到文件"""
    global configCache
    config_path = os.path.join(get_base_path(), CONFIG_FILE)
    try:
        configCache = {
            "hotkeys": currentHotkeys,
            "presets": currentPresets,
            "showBackgroundImage": showBackgroundImage,
            "showCloseButton": showCloseButton,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(configCache, f, ensure_ascii=False, indent=2)
        print(f"配置已保存")
    except Exception as e:
        print(f"保存配置失败: {e}")


def check_single_instance():
    """检查是否已有实例运行"""
    global SINGLE_INSTANCE_LOCK
    try:
        SINGLE_INSTANCE_LOCK = win32event.CreateMutex(
            None, False, "RukkScreenFilter_SingleInstance"  # type: ignore
        )
        if win32api.GetLastError() == 183:
            print("程序已在运行中，请勿重复启动！")
            return False
        return True
    except (ImportError, AttributeError):
        pass
    return True

    lock_file = os.path.join(get_base_path(), ".single_instance.lock")
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                pid = int(f.read().strip())
            if psutil.pid_exists(pid):
                print("程序已在运行中，请勿重复启动！")
                return False
        except (ValueError, psutil.NoSuchProcess):
            pass
        except ImportError:
            print("程序已在运行中，请勿重复启动！")
            return False

    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_single_instance():
    """释放单实例锁"""
    global SINGLE_INSTANCE_LOCK
    if SINGLE_INSTANCE_LOCK:
        try:
            win32api.CloseHandle(SINGLE_INSTANCE_LOCK)
        except:
            pass

    lock_file = os.path.join(get_base_path(), ".single_instance.lock")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except:
            pass


def register_global_hotkeys():
    """注册全局快捷键"""
    global registeredHotkeys
    unregister_global_hotkeys()

    try:
        registeredHotkeys = []

        hotkey_actions = {
            "increaseIntensity": lambda: trigger_hotkey_action("increaseIntensity"),
            "decreaseIntensity": lambda: trigger_hotkey_action("decreaseIntensity"),
            "increaseBrightness": lambda: trigger_hotkey_action("increaseBrightness"),
            "decreaseBrightness": lambda: trigger_hotkey_action("decreaseBrightness"),
            "nextPreset": lambda: trigger_hotkey_action("nextPreset"),
            "prevPreset": lambda: trigger_hotkey_action("prevPreset"),
            "toggleFilter": lambda: trigger_hotkey_action("toggleFilter"),
            "toggleWindow": lambda: trigger_hotkey_action("toggleWindow"),
            "turnOffScreen": lambda: trigger_hotkey_action("turnOffScreen"),
        }

        for key, action in hotkey_actions.items():
            hotkey = currentHotkeys.get(key, "")
            if hotkey:
                try:
                    keyboard.register_hotkey(hotkey, action)
                    registeredHotkeys.append(hotkey)
                    print(f"已注册快捷键: {hotkey} -> {key}")
                except Exception as e:
                    print(f"注册快捷键失败 {hotkey}: {e}")

    except NameError:
        print("keyboard模块未安装，全局快捷键将不起作用")


def unregister_global_hotkeys():
    """取消注册所有全局快捷键"""
    global registeredHotkeys
    try:
        for hotkey in registeredHotkeys:
            try:
                keyboard.unregister_hotkey(hotkey)
                print(f"已取消注册快捷键: {hotkey}")
            except Exception as e:
                print(f"取消注册快捷键失败 {hotkey}: {e}")
        registeredHotkeys = []
    except NameError:
        pass


def trigger_hotkey_action(action_type: str):
    """触发快捷键动作"""

    def do_action():
        try:
            if webview.windows:
                webview.windows[0].evaluate_js(
                    f"window.onHotkey && window.onHotkey('{action_type}')"
                )
        except Exception as e:
            print(f"执行快捷键动作失败 {action_type}: {e}")

    thread = threading.Thread(target=do_action)
    thread.daemon = True
    thread.start()


class ScreenFilter:
    """
    屏幕滤镜控制类
    实现RGB颜色滤镜、亮度滤镜和系统亮度的控制
    """

    def __init__(self):
        """初始化屏幕滤镜控制器"""
        # 当前设置状态
        self.current_rgb: List[int] = [0, 0, 0]
        self.current_brightness_filter: int = 0
        self.current_intensity: int = 50

        # Windows API 相关
        self.user32 = None
        self.hdc = None
        self._init_windows_api()

    def _init_windows_api(self) -> None:
        """初始化Windows API"""
        try:
            self.user32 = ctypes.windll.user32
            self.gdi32 = ctypes.windll.gdi32
            self.hdc = self.user32.GetDC(0)

            # 定义 SetDeviceGammaRamp 函数原型
            # BOOL SetDeviceGammaRamp(HDC hdc, LPVOID lpRamp)
            self.gdi32.SetDeviceGammaRamp.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            self.gdi32.SetDeviceGammaRamp.restype = ctypes.c_bool

            print("Windows API 初始化成功")
        except Exception as e:
            print(f"Windows API 初始化失败: {e}")
            raise

    def apply_color_filter(
        self,
        rgb_color: List[int],
        brightness_filter: int,
        intensity: int = 50,
        gamma: float = 1.0,
    ) -> bool:
        """
        应用RGB颜色滤镜到屏幕

        Args:
            rgb_color: RGB颜色值列表 [R, G, B]，范围 0-255
            brightness_filter: 亮度滤镜值，范围 0-90
            intensity: 滤镜强度（透明度），范围 0-100，值越小越透明
            gamma: 伽马值，默认1.0

        Returns:
            bool: 是否应用成功
        """
        try:
            if not self.user32 or not self.hdc:
                print("Windows API 未初始化")
                return False

            # 参数校验和限制
            rgb_color = [max(30, min(255, c)) for c in rgb_color]
            brightness_filter = max(0, min(90, brightness_filter))
            intensity = max(0, min(100, intensity))

            # 计算透明度因子（intensity越小越透明）
            alpha = intensity / 100.0

            # 创建gamma ramp数组（3个通道，每个256个值）
            ramp = (256 * 3 * ctypes.c_ushort)()

            for i in range(256):
                # 基础gamma曲线值
                base_value = int(255 * pow(i / 255, gamma))

                # 应用颜色滤镜（根据透明度混合原始值和目标颜色）
                r_value = int(
                    base_value * (1 - alpha) + (base_value * rgb_color[0] / 255) * alpha
                )
                g_value = int(
                    base_value * (1 - alpha) + (base_value * rgb_color[1] / 255) * alpha
                )
                b_value = int(
                    base_value * (1 - alpha) + (base_value * rgb_color[2] / 255) * alpha
                )

                # 应用亮度滤镜（黑色蒙层，值越大越暗）
                # brightness_filter: 0 = 不变暗, 90 = 最强变暗（接近全黑）
                brightness_factor = 1 - (brightness_filter / 100.0)
                r_value = int(r_value * brightness_factor)
                g_value = int(g_value * brightness_factor)
                b_value = int(b_value * brightness_factor)

                # 填充gamma ramp（转换为16位值）
                ramp[i] = r_value << 8
                ramp[256 + i] = g_value << 8
                ramp[512 + i] = b_value << 8

            # 应用gamma ramp到屏幕（SetDeviceGammaRamp 属于 gdi32）
            result = self.gdi32.SetDeviceGammaRamp(self.hdc, ctypes.byref(ramp))

            if result:
                # 更新当前设置
                self.current_rgb = rgb_color.copy()
                self.current_brightness_filter = brightness_filter
                self.current_intensity = intensity
                print(
                    f"滤镜应用成功: RGB={rgb_color}, 亮度={brightness_filter}, 强度={intensity}"
                )
                return True
            else:
                print("SetDeviceGammaRamp 调用失败")
                return False

        except Exception as e:
            print(f"应用滤镜时发生错误: {e}")
            return False

    def get_current_settings(self) -> Dict:
        """
        获取当前所有设置

        Returns:
            dict: 包含当前设置的字典
        """
        return {
            "rgb": self.current_rgb.copy(),
            "brightnessFilter": self.current_brightness_filter,
            "intensity": self.current_intensity,
        }

    def reset_filter(self) -> bool:
        """
        重置滤镜到默认状态（无滤镜）

        Returns:
            bool: 是否重置成功
        """
        return self.apply_color_filter([0, 0, 0], 0, 0)


class Api:
    """
    PyWebview API类
    暴露给JavaScript调用的接口方法
    """

    def __init__(self, filter_controller: ScreenFilter):
        """
        初始化API接口

        Args:
            filter_controller: 屏幕滤镜控制器实例
        """
        self.filter = filter_controller

    def apply_filter(
        self, rgb: List[int], brightness_filter: int, intensity: int
    ) -> str:
        """
        应用滤镜设置（供JS调用）

        Args:
            rgb: RGB颜色值列表 [R, G, B]
            brightness_filter: 亮度滤镜值
            intensity: 滤镜强度

        Returns:
            str: 操作结果消息
        """
        success = self.filter.apply_color_filter(rgb, brightness_filter, intensity)
        return "success" if success else "failed"

    def get_current_settings(self) -> Dict:
        """
        获取当前设置（供JS调用）

        Returns:
            dict: 当前设置字典
        """
        return self.filter.get_current_settings()

    def reset_all(self) -> str:
        """
        重置所有设置（供JS调用）

        Returns:
            str: 操作结果消息
        """
        success = self.filter.reset_filter()
        return "success" if success else "failed"

    def toggle_filter(self) -> str:
        """
        切换滤镜开关状态（供JS调用）

        Returns:
            str: 操作结果消息
        """
        global filterEnabled
        filterEnabled = not filterEnabled
        if filterEnabled:
            current = self.filter.get_current_settings()
            self.filter.apply_color_filter(
                current["rgb"], current["brightnessFilter"], current["intensity"]
            )
        else:
            self.filter.reset_filter()
        return "success" if filterEnabled else "disabled"

    def get_filter_enabled(self) -> bool:
        """
        获取滤镜开关状态（供JS调用）

        Returns:
            bool: 滤镜是否启用
        """
        return filterEnabled

    def minimize_window(self) -> str:
        """
        最小化窗口到托盘（供JS调用）

        Returns:
            str: 操作结果消息
        """
        try:
            if webview.windows:
                webview.windows[0].hide()
            return "success"
        except Exception as e:
            print(f"最小化窗口失败: {e}")
            return "failed"

    def close_window(self) -> str:
        """
        关闭窗口（供JS调用）
        """
        try:
            self.filter.reset_filter()
            if webview.windows:
                webview.windows[0].destroy()
            return "success"
        except Exception as e:
            print(f"关闭窗口失败: {e}")
            return "failed"

    def turn_off_screen_api(self) -> str:
        """
        熄屏（供JS调用）
        """
        turn_off_screen()
        return "success"

    def get_hotkey_settings(self) -> Dict:
        """
        获取快捷键设置（供JS调用）

        Returns:
            dict: 当前快捷键设置
        """
        return currentHotkeys

    def save_hotkey_settings(self, settings: Dict) -> str:
        """
        保存快捷键设置（供JS调用）

        Args:
            settings: 快捷键设置字典

        Returns:
            str: 操作结果消息
        """
        global currentHotkeys
        try:
            currentHotkeys = settings.copy()
            save_config()
            register_global_hotkeys()
            return "success"
        except Exception as e:
            print(f"保存快捷键设置失败: {e}")
            return "failed"

    def onHotkey(self, action_type: str) -> str:
        """
        快捷键触发回调（供前端调用）

        Args:
            action_type: 动作类型

        Returns:
            str: 操作结果消息
        """
        print(f"快捷键触发: {action_type}")
        try:
            if webview.windows:
                webview.windows[0].evaluate_js(
                    f"window.onHotkey && window.onHotkey('{action_type}')"
                )
        except Exception as e:
            print(f"调用前端onHotkey失败: {e}")
        return "success"

    def get_presets(self) -> List[Dict]:
        """
        获取预设列表（供JS调用）

        Returns:
            list: 预设列表
        """
        global currentPresets
        if currentPresets is None:
            load_config()
        assert currentPresets is not None
        return currentPresets

    def save_presets(self, presets: List) -> str:
        """
        保存预设列表（供JS调用）

        Args:
            presets: 预设列表

        Returns:
            str: 操作结果消息
        """
        global currentPresets
        try:
            currentPresets = presets
            save_config()
            return "success"
        except Exception as e:
            print(f"保存预设失败: {e}")
            return "failed"

    def show_hotkey_settings(self) -> str:
        """
        显示快捷键设置界面（供托盘调用）

        Returns:
            str: 操作结果消息
        """
        try:
            if webview.windows:
                webview.windows[0].show()
                webview.windows[0].focus = True
                webview.windows[0].evaluate_js(
                    "window.showHotkeyModal && window.showHotkeyModal()"
                )
            return "success"
        except Exception as e:
            print(f"显示快捷键设置失败: {e}")
            return "failed"

    def disable_hotkeys(self) -> str:
        """
        禁用所有全局快捷键（供JS调用，编辑快捷键时使用）

        Returns:
            str: 操作结果消息
        """
        try:
            unregister_global_hotkeys()
            return "success"
        except Exception as e:
            print(f"禁用快捷键失败: {e}")
            return "failed"

    def enable_hotkeys(self) -> str:
        """
        重新启用所有全局快捷键（供JS调用，编辑快捷键结束后使用）

        Returns:
            str: 操作结果消息
        """
        try:
            register_global_hotkeys()
            return "success"
        except Exception as e:
            print(f"启用快捷键失败: {e}")
            return "failed"

    def toggle_window(self) -> str:
        """
        切换窗口显示/隐藏状态（供JS调用）

        Returns:
            str: 操作结果消息
        """
        global WINDOW_VISIBLE
        try:
            if webview.windows:
                if WINDOW_VISIBLE:
                    webview.windows[0].hide()
                    WINDOW_VISIBLE = False
                else:
                    webview.windows[0].show()
                    user32 = ctypes.windll.user32
                    win_id = user32.FindWindowW(None, "屏幕护眼工具")
                    if win_id:
                        SWP_NOSIZE = 0x0001
                        SWP_NOMOVE = 0x0002
                        SWP_SHOWWINDOW = 0x0040
                        HWND_TOPMOST = ctypes.c_void_p(-1)
                        user32.SetWindowPos(
                            win_id,
                            HWND_TOPMOST,
                            0,
                            0,
                            0,
                            0,
                            SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW,
                        )
                        user32.SetForegroundWindow(win_id)
                        user32.SetActiveWindow(win_id)
                    WINDOW_VISIBLE = True
            return "success"
        except Exception as e:
            print(f"切换窗口状态失败: {e}")
            return "failed"

    def toggle_background_image(self) -> str:
        """
        切换背景图显示/隐藏状态（供托盘调用）

        Returns:
            str: 操作结果消息
        """
        global showBackgroundImage
        try:
            showBackgroundImage = not showBackgroundImage
            save_config()
            if webview.windows:
                webview.windows[0].evaluate_js(
                    f"window.updateBackgroundImage && window.updateBackgroundImage({str(showBackgroundImage).lower()})"
                )
            return "success" if showBackgroundImage else "hidden"
        except Exception as e:
            print(f"切换背景图状态失败: {e}")
            return "failed"

    def get_background_image_enabled(self) -> bool:
        """
        获取背景图显示状态（供前端调用）

        Returns:
            bool: 背景图是否显示
        """
        return showBackgroundImage

    def toggle_close_button(self) -> str:
        """
        切换关闭按钮显示/隐藏状态（供托盘调用）

        Returns:
            str: 操作结果消息
        """
        global showCloseButton
        try:
            showCloseButton = not showCloseButton
            save_config()
            print(f"切换关闭按钮状态: {showCloseButton}")
            if webview.windows:
                js_code = f"window.updateCloseButtonVisibility && window.updateCloseButtonVisibility({str(showCloseButton).lower()})"
                print(f"执行JS: {js_code}")
                webview.windows[0].evaluate_js(js_code)
            return "success" if showCloseButton else "hidden"
        except Exception as e:
            print(f"切换关闭按钮状态失败: {e}")
            return "failed"

    def get_close_button_enabled(self) -> bool:
        """
        获取关闭按钮显示状态（供前端调用）

        Returns:
            bool: 关闭按钮是否显示
        """
        return showCloseButton


def turn_off_screen():
    """关闭屏幕（移动鼠标会自动亮屏）"""
    try:
        user32 = ctypes.windll.user32
        user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        print("屏幕已关闭")
    except Exception as e:
        print(f"关闭屏幕失败: {e}")


def start_application():
    """启动应用程序"""
    if not check_single_instance():
        sys.exit(1)

    filter_controller = ScreenFilter()
    api = Api(filter_controller)

    load_config()
    register_global_hotkeys()

    html_path = get_resource_path(os.path.join("vue-web", "index.html"))

    if not os.path.exists(html_path):
        print(f"HTML文件不存在: {html_path}")
        sys.exit(1)

    user32 = ctypes.windll.user32
    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)
    window_width = 700
    window_height = 500
    x = (screen_width / 2) - (window_width) + 120
    y = (screen_height / 2) - (window_height) + 82
    print(f"窗口位置: ({screen_width}, {screen_height})")
    print(f"窗口位置: ({window_width}, {window_height})")

    window_config = {
        "title": "Rukk Filter",
        "url": html_path,
        "width": window_width,
        "height": window_height,
        "x": x,
        "y": y,
        "min_size": (window_width, window_height),
        "resizable": False,
        "frameless": True,
        "easy_drag": False,
        "background_color": "#FFFFFF",
        "js_api": api,
    }

    def on_quit_callback(icon, item):
        print("退出程序")
        filter_controller.reset_filter()
        release_single_instance()
        if icon:
            icon.stop()
        if webview.windows:
            webview.windows[0].destroy()
        os._exit(0)

    def show_window_callback(icon, item):
        global WINDOW_VISIBLE
        if webview.windows:
            webview.windows[0].show()
            webview.windows[0].focus = True
            WINDOW_VISIBLE = True

    def on_tray_activate(icon):
        global WINDOW_VISIBLE
        if webview.windows:
            if WINDOW_VISIBLE:
                webview.windows[0].hide()
                WINDOW_VISIBLE = False
            else:
                webview.windows[0].show()
                webview.windows[0].focus = True
                WINDOW_VISIBLE = True

    def create_tray_icon():
        icon_ico_path = get_resource_path(ICON)
        if os.path.exists(icon_ico_path):
            image = Image.open(icon_ico_path)
            image = image.resize((256, 256), Image.Resampling.LANCZOS)
        else:
            image = Image.new("RGB", (256, 256), color="green")

        def make_hotkey_callback(action_type):
            def callback(icon, item):
                show_window_callback(icon, item)

                def delayed_action():
                    time.sleep(0.3)
                    trigger_hotkey_action(action_type)

                thread = threading.Thread(target=delayed_action)
                thread.daemon = True
                thread.start()

            return callback

        def on_single_click(icon, item):
            on_tray_activate(icon)

        menu = pystray.Menu(
            pystray.MenuItem(
                "显示/隐藏窗口",
                on_single_click,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "快捷键设置", lambda icon, item: api.show_hotkey_settings()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "滤镜开关", lambda icon, item: trigger_hotkey_action("toggleFilter")
            ),
            pystray.MenuItem(
                "显示/隐藏背景图", lambda icon, item: api.toggle_background_image()
            ),
            pystray.MenuItem(
                "显示/隐藏关闭按钮", lambda icon, item: api.toggle_close_button()
            ),
            pystray.MenuItem("熄屏", lambda icon, item: turn_off_screen()),
            pystray.MenuItem("切换上一个预设", make_hotkey_callback("prevPreset")),
            pystray.MenuItem("切换下一个预设", make_hotkey_callback("nextPreset")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_quit_callback),
        )

        icon = pystray.Icon("screen_filter", image, "Rukk Filter", menu)
        icon.on_activate = on_tray_activate  # type: ignore
        return icon

    tray_icon = create_tray_icon()

    def run_tray():
        tray_icon.run()

    tray_thread = threading.Thread(target=run_tray, daemon=True)
    tray_thread.start()

    try:
        window = webview.create_window(**window_config)
        print("屏幕护眼工具启动成功")
        print(f"HTML路径: {html_path}")
        webview.start(debug=DEBUG, icon=ICON)
    except Exception as e:
        print(f"启动应用程序失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_application()
