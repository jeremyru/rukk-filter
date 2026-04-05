"""
屏幕护眼工具 - PyWebview版本
使用 pywebview 作为GUI框架，实现RGB颜色滤镜、亮度滤镜和系统亮度控制功能
"""

import os
import sys
import ctypes
import json
import webview
from typing import Dict, List

DEBUG = False
ICON = "logo.png"

SINGLE_INSTANCE_LOCK = None

HOTKEY_CONFIG_FILE = "hotkey_settings.json"

DEFAULT_HOTKEYS = {
    "increaseIntensity": "ctrl+right",
    "decreaseIntensity": "ctrl+left",
    "increaseBrightness": "ctrl+up",
    "decreaseBrightness": "ctrl+down",
    "nextPreset": "alt+right",
    "prevPreset": "alt+left",
    "toggleFilter": "alt+down",
}

currentHotkeys = DEFAULT_HOTKEYS.copy()

registeredHotkeys = []

CONFIG_FILE = "config.json"

filterEnabled = True

DEFAULT_PRESETS = [
    {"name": "默认", "rgb": [255, 180, 120], "intensity": 50, "brightnessFilter": 0},
    {"name": "护眼", "rgb": [255, 230, 180], "intensity": 50, "brightnessFilter": 0},
    {"name": "夜晚", "rgb": [255, 120, 80], "intensity": 70, "brightnessFilter": 20},
    {"name": "深夜", "rgb": [255, 80, 60], "intensity": 80, "brightnessFilter": 40},
]

currentPresets = None

configCache = {}


def load_config():
    """从文件加载配置（包含快捷键和预设）"""
    global currentHotkeys, currentPresets, configCache
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                configCache = json.load(f)
            currentHotkeys = configCache.get('hotkeys', DEFAULT_HOTKEYS.copy())
            currentPresets = configCache.get('presets', json.loads(json.dumps(DEFAULT_PRESETS)))
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
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
    try:
        configCache = {
            'hotkeys': currentHotkeys,
            'presets': currentPresets
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(configCache, f, ensure_ascii=False, indent=2)
        print(f"配置已保存")
    except Exception as e:
        print(f"保存配置失败: {e}")


def check_single_instance():
    """检查是否已有实例运行"""
    global SINGLE_INSTANCE_LOCK
    try:
        import win32event
        import win32api
        import pywintypes

        SINGLE_INSTANCE_LOCK = win32event.CreateMutex(None, False, "RukkScreenFilter_SingleInstance")
        if win32api.GetLastError() == 183:
            print("程序已在运行中，请勿重复启动！")
            return False
        return True
    except (ImportError, AttributeError):
        pass

    lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.single_instance.lock')
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                pid = int(f.read().strip())
            import psutil
            if psutil.pid_exists(pid):
                print("程序已在运行中，请勿重复启动！")
                return False
        except (ValueError, psutil.NoSuchProcess):
            pass
        except ImportError:
            print("程序已在运行中，请勿重复启动！")
            return False

    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))
    return True


def release_single_instance():
    """释放单实例锁"""
    global SINGLE_INSTANCE_LOCK
    if SINGLE_INSTANCE_LOCK:
        try:
            import win32api
            win32api.CloseHandle(SINGLE_INSTANCE_LOCK)
        except:
            pass

    lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.single_instance.lock')
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except:
            pass


def load_hotkey_settings():
    """从文件加载快捷键设置"""
    global currentHotkeys
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), HOTKEY_CONFIG_FILE)
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                currentHotkeys = json.load(f)
            print(f"快捷键设置已加载: {currentHotkeys}")
        else:
            currentHotkeys = DEFAULT_HOTKEYS.copy()
            save_hotkey_settings()
    except Exception as e:
        print(f"加载快捷键设置失败: {e}")
        currentHotkeys = DEFAULT_HOTKEYS.copy()


def save_hotkey_settings():
    """保存快捷键设置到文件"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), HOTKEY_CONFIG_FILE)
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(currentHotkeys, f, ensure_ascii=False, indent=2)
        print(f"快捷键设置已保存: {currentHotkeys}")
    except Exception as e:
        print(f"保存快捷键设置失败: {e}")


def register_global_hotkeys():
    """注册全局快捷键"""
    global registeredHotkeys
    unregister_global_hotkeys()

    try:
        import keyboard
        registeredHotkeys = []

        hotkey_actions = {
            "increaseIntensity": lambda: trigger_hotkey_action("increaseIntensity"),
            "decreaseIntensity": lambda: trigger_hotkey_action("decreaseIntensity"),
            "increaseBrightness": lambda: trigger_hotkey_action("increaseBrightness"),
            "decreaseBrightness": lambda: trigger_hotkey_action("decreaseBrightness"),
            "nextPreset": lambda: trigger_hotkey_action("nextPreset"),
            "prevPreset": lambda: trigger_hotkey_action("prevPreset"),
            "toggleFilter": lambda: trigger_hotkey_action("toggleFilter"),
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

    except ImportError:
        print("keyboard模块未安装，全局快捷键将不起作用")


def unregister_global_hotkeys():
    """取消注册所有全局快捷键"""
    global registeredHotkeys
    try:
        import keyboard
        for hotkey in registeredHotkeys:
            try:
                keyboard.unregister_hotkey(hotkey)
                print(f"已取消注册快捷键: {hotkey}")
            except Exception as e:
                print(f"取消注册快捷键失败 {hotkey}: {e}")
        registeredHotkeys = []
    except ImportError:
        pass


def trigger_hotkey_action(action_type: str):
    """触发快捷键动作"""
    import threading
    def do_action():
        try:
            if webview.windows:
                webview.windows[0].evaluate_js(f"window.onHotkey && window.onHotkey('{action_type}')")
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
        gamma: float = 1.0
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
                r_value = int(base_value * (1 - alpha) + (base_value * rgb_color[0] / 255) * alpha)
                g_value = int(base_value * (1 - alpha) + (base_value * rgb_color[1] / 255) * alpha)
                b_value = int(base_value * (1 - alpha) + (base_value * rgb_color[2] / 255) * alpha)

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
                print(f"滤镜应用成功: RGB={rgb_color}, 亮度={brightness_filter}, 强度={intensity}")
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
            'rgb': self.current_rgb.copy(),
            'brightnessFilter': self.current_brightness_filter,
            'intensity': self.current_intensity
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

    def apply_filter(self, rgb: List[int], brightness_filter: int, intensity: int) -> str:
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
            self.filter.apply_color_filter(current['rgb'], current['brightnessFilter'], current['intensity'])
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
            import webview
            if webview.windows:
                webview.windows[0].hide()
            return "success"
        except Exception as e:
            print(f"最小化窗口失败: {e}")
            return "failed"

    def close_window(self) -> str:
        """
        关闭窗口（供JS调用）

        Returns:
            str: 操作结果消息
        """
        try:
            self.filter.reset_filter()
            import webview
            if webview.windows:
                webview.windows[0].destroy()
            return "success"
        except Exception as e:
            print(f"关闭窗口失败: {e}")
            return "failed"

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

    def on_hotkey_triggered(self, action_type: str) -> str:
        """
        快捷键触发回调（供内部调用）

        Args:
            action_type: 动作类型

        Returns:
            str: 操作结果消息
        """
        print(f"快捷键触发: {action_type}")
        return "success"

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
                webview.windows[0].evaluate_js(f"window.onHotkey && window.onHotkey('{action_type}')")
        except Exception as e:
            print(f"调用前端onHotkey失败: {e}")
        return "success"

    def get_presets(self) -> List:
        """
        获取预设列表（供JS调用）

        Returns:
            list: 预设列表
        """
        global currentPresets
        if currentPresets is None:
            load_config()
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
            import webview
            if webview.windows:
                webview.windows[0].show()
                webview.windows[0].focus = True
                webview.windows[0].evaluate_js("window.showHotkeyModal && window.showHotkeyModal()")
            return "success"
        except Exception as e:
            print(f"显示快捷键设置失败: {e}")
            return "failed"


def start_application():
    """启动应用程序"""
    if not check_single_instance():
        sys.exit(1)

    import threading
    from PIL import Image
    import pystray

    filter_controller = ScreenFilter()
    api = Api(filter_controller)

    load_config()
    register_global_hotkeys()

    html_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'vue-web',
        'index.html'
    )

    if not os.path.exists(html_path):
        print(f"HTML文件不存在: {html_path}")
        sys.exit(1)

    window_config = {
        'title': '屏幕护眼工具',
        'url': html_path,
        'width': 700,
        'height': 500,
        'min_size': (700, 500),
        'resizable': False,
        'frameless': True,
        'easy_drag': False,
        'background_color': '#FFFFFF',
        'js_api': api
    }

    def on_quit_callback(icon, item):
        print("退出程序")
        filter_controller.reset_filter()
        release_single_instance()
        if icon:
            icon.stop()
        import webview
        if webview.windows:
            webview.windows[0].destroy()
        os._exit(0)

    def show_window_callback(icon, item):
        import webview
        if webview.windows:
            webview.windows[0].show()
            webview.windows[0].focus = True

    def on_tray_activate(icon):
        import webview
        if webview.windows:
            webview.windows[0].show()
            webview.windows[0].focus = True

    def create_tray_icon():
        icon_ico_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ICON
        )
        if os.path.exists(icon_ico_path):
            image = Image.open(icon_ico_path)
            image = image.resize((256, 256), Image.Resampling.LANCZOS)
        else:
            image = Image.new('RGB', (256, 256), color='green')

        def make_hotkey_callback(action_type):
            def callback(icon, item):
                show_window_callback(icon, item)
                def delayed_action():
                    import time
                    time.sleep(0.3)
                    trigger_hotkey_action(action_type)
                thread = threading.Thread(target=delayed_action)
                thread.daemon = True
                thread.start()
            return callback

        menu = pystray.Menu(
            pystray.MenuItem("显示主窗口", show_window_callback, default=True),
            pystray.MenuItem("快捷键设置", lambda icon, item: api.show_hotkey_settings()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("滤镜开关", lambda icon, item: trigger_hotkey_action("toggleFilter")),
            pystray.MenuItem("切换上一个预设", make_hotkey_callback("prevPreset")),
            pystray.MenuItem("切换下一个预设", make_hotkey_callback("nextPreset")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_quit_callback)
        )

        icon = pystray.Icon("screen_filter", image, "屏幕护眼工具", menu)
        icon.on_activate = on_tray_activate
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
        webview.start(debug=DEBUG,icon=ICON)
    except Exception as e:
        print(f"启动应用程序失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    start_application()
