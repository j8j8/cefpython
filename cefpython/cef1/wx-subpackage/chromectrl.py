# Additional and wx specific layer of abstraction for the cefpython
# __author__ = "Greg Kacy <grkacy@gmail.com>"

#--------------------------------------------------------------------------------

import platform
if platform.architecture()[0] != "32bit":
    raise Exception("Only 32bit architecture is supported")

import os
import sys
try:
    # Import local PYD file (portable zip).
    if sys.hexversion >= 0x02070000 and sys.hexversion < 0x03000000:
        import cefpython_py27 as cefpython
    elif sys.hexversion >= 0x03000000 and sys.hexversion < 0x04000000:
        import cefpython_py32 as cefpython
    else:
        raise Exception("Unsupported python version: %s" % sys.version)
except ImportError:
    # Import from package (installer).
    from cefpython1 import cefpython

import wx
import wx.lib.buttons as buttons

from cefpython1.wx.utils import GetApplicationPath

#-------------------------------------------------------------------------------

# Default timer interval when timer used to service CEF message loop
DEFAULT_TIMER_MILLIS = 10

#-------------------------------------------------------------------------------

class NavigationBar(wx.Panel):
    def __init__(self, parent, *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)

        self.bitmapDir = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "images")

        self._InitComponents()
        self._LayoutComponents()
        self._InitEventHandlers()

    def _InitComponents(self):
        self.backBtn = buttons.GenBitmapButton(self, -1,
                wx.Bitmap(os.path.join(self.bitmapDir, "Arrow Left.png"),
                          wx.BITMAP_TYPE_PNG), style=wx.BORDER_NONE)
        self.forwardBtn = buttons.GenBitmapButton(self, -1,
                wx.Bitmap(os.path.join(self.bitmapDir, "Arrow Right.png"),
                          wx.BITMAP_TYPE_PNG), style=wx.BORDER_NONE)
        self.reloadBtn = buttons.GenBitmapButton(self, -1,
                wx.Bitmap(os.path.join(self.bitmapDir, "Button Load.png"),
                          wx.BITMAP_TYPE_PNG), style=wx.BORDER_NONE)

        self.url = wx.TextCtrl(self, id=-1, style=0)

        self.historyPopup = wx.Menu()

    def _LayoutComponents(self):
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.backBtn, 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|
                  wx.ALL, 0)
        sizer.Add(self.forwardBtn, 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|
                  wx.ALL, 0)
        sizer.Add(self.reloadBtn, 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|
                  wx.ALL, 0)

        sizer.Add(self.url, 1, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 12)

        self.SetSizer(sizer)
        self.Fit()

    def _InitEventHandlers(self):
        self.backBtn.Bind(wx.EVT_CONTEXT_MENU, self.OnButtonContext)

    def __del__(self):
        self.historyPopup.Destroy()

    def GetBackButton(self):
        return self.backBtn

    def GetForwardButton(self):
        return self.forwardBtn

    def GetReloadButton(self):
        return self.reloadBtn

    def GetUrlCtrl(self):
        return self.url

    def InitHistoryPopup(self):
        self.historyPopup = wx.Menu()

    def AddToHistory(self, url):
        self.historyPopup.Append(-1, url)

    def OnButtonContext(self, event):
        self.PopupMenu(self.historyPopup)


class ChromeWindow(wx.Window):
    """
    Standalone CEF component. The class provides facilites for interacting
    with wx message loop
    """
    def __init__(self, parent, url="", useTimer=False,
                 timerMillis=DEFAULT_TIMER_MILLIS,  size=(-1, -1),
                 *args, **kwargs):
        wx.Window.__init__(self, parent, id=wx.ID_ANY, size=size,
                           *args, **kwargs)
        self.url = url
        windowInfo = cefpython.WindowInfo()
        windowInfo.SetAsChild(self.GetHandle())
        self.browser = cefpython.CreateBrowserSync(windowInfo,
                browserSettings={}, navigateUrl=url)

        self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        if useTimer:
            self.timerID = 1
            self._CreateTimer(timerMillis)
        else:
            self.Bind(wx.EVT_IDLE, self.OnIdle)
        self._useTimer = useTimer

    def __del__(self):
        '''cleanup stuff'''
        if self._useTimer:
            self.timer.Stop()
        else:
            self.Unbind(wx.EVT_IDLE)
        self.browser.CloseBrowser()

    def _CreateTimer(self, millis):
        self.timer = wx.Timer(self, self.timerID)
        self.timer.Start(millis) #
        wx.EVT_TIMER(self, self.timerID, self.OnTimer)

    def OnTimer(self, event):
        """Service CEF message loop when useTimer is True"""
        cefpython.MessageLoopWork()

    def OnIdle(self, event):
        """Service CEF message loop when useTimer is False"""
        cefpython.MessageLoopWork()
        event.Skip()

    def OnSetFocus(self, event):
        cefpython.WindowUtils.OnSetFocus(self.GetHandle(), 0, 0, 0)
        event.Skip()

    def OnSize(self, event):
        """Handle the the size event"""
        cefpython.WindowUtils.OnSize(self.GetHandle(), 0, 0, 0)
        event.Skip()

    def GetBrowser(self):
        """Returns the CEF's browser object"""
        return self.browser

    def LoadUrl(self, url, onLoadStart=None, onLoadEnd=None):
        if onLoadStart or onLoadEnd:
            self.GetBrowser().SetClientHandler(
                CallbackClientHandler(onLoadStart, onLoadEnd))
        self.GetBrowser().GetMainFrame().LoadUrl(url)


class ChromeCtrl(wx.Panel):
    def __init__(self, parent, url="", useTimer=False,
                 timerMillis=DEFAULT_TIMER_MILLIS, hasNavBar=True,
                 *args, **kwargs):
        wx.Panel.__init__(self, parent, *args, **kwargs)

        self.chromeWindow = ChromeWindow(self, url=str(url), useTimer=useTimer)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.navigationBar = None
        if hasNavBar:
            self.navigationBar = self.CreateNavigationBar()
            sizer.Add(self.navigationBar, 0, wx.EXPAND|wx.ALL, 0)
            self._InitEventHandlers()

        sizer.Add(self.chromeWindow, 1, wx.EXPAND, 0)

        self.SetSizer(sizer)
        self.Fit()

        ch = DefaultClientHandler(self)
        self.SetClientHandler(ch)
        if self.navigationBar:
            self.UpdateButtonsState()

    def _InitEventHandlers(self):
        self.navigationBar.backBtn.Bind(wx.EVT_BUTTON, self.OnLeft)
        self.navigationBar.forwardBtn.Bind(wx.EVT_BUTTON, self.OnRight)
        self.navigationBar.reloadBtn.Bind(wx.EVT_BUTTON, self.OnReload)

    def GetNavigationBar(self):
        return self.navigationBar

    def SetNavigationBar(self, navigationBar):
        sizer = self.GetSizer()
        if self.navigationBar:
            # remove previous one
            sizer.Replace(self.navigationBar, navigationBar)
            self.navigationBar.Hide()
            del self.navigationBar
        else:
            sizer.Insert(0, navigationBar, 0, wx.EXPAND)
        self.navigationBar = navigationBar
        sizer.Fit(self)

    def CreateNavigationBar(self):
        np = NavigationBar(self)
        return np

    def SetClientHandler(self, handler):
        self.chromeWindow.GetBrowser().SetClientHandler(handler)

    def OnLeft(self, event):
        if self.chromeWindow.GetBrowser().CanGoBack():
            self.chromeWindow.GetBrowser().GoBack()
        self.UpdateButtonsState()

    def OnRight(self, event):
        if self.chromeWindow.GetBrowser().CanGoForward():
            self.chromeWindow.GetBrowser().GoForward()
        self.UpdateButtonsState()

    def OnReload(self, event):
        self.chromeWindow.GetBrowser().Reload()
        self.UpdateButtonsState()

    def UpdateButtonsState(self):
        self.navigationBar.backBtn.Enable(
            self.chromeWindow.GetBrowser().CanGoBack())
        self.navigationBar.forwardBtn.Enable(
            self.chromeWindow.GetBrowser().CanGoForward())

    def OnLoadStart(self, browser, frame):
        if self.navigationBar:
            self.UpdateButtonsState()
            self.navigationBar.GetUrlCtrl().SetValue(
                browser.GetMainFrame().GetUrl())
            self.navigationBar.AddToHistory(browser.GetMainFrame().GetUrl())


class DefaultClientHandler(object):
    def __init__(self, parentCtrl):
        self.parentCtrl = parentCtrl

    def OnLoadStart(self, browser, frame):
        self.parentCtrl.OnLoadStart(browser, frame)

    def OnLoadEnd(self, browser, frame, httpStatusCode):
        self.parentCtrl.OnLoadEnd(browser, frame, httpStatusCode)

    def OnLoadError(self, browser, frame, errorCode, failedUrl, errorText):
        # TODO
        print "ERROR LOADING URL : %" % failedUrl

class CallbackClientHandler(object):
    def __init__(self, onLoadStart=None, onLoadEnd=None):
        self.onLoadStart = onLoadStart
        self.onLoadEnd = onLoadEnd

    def OnLoadStart(self, browser, frame):
        if self.onLoadStart and frame.GetUrl() != "about:blank":
            self.onLoadStart(browser, frame)

    def OnLoadEnd(self, browser, frame, httpStatusCode):
        if self.onLoadEnd and frame.GetUrl() != "about:blank":
            self.onLoadEnd(browser, frame, httpStatusCode)

    def OnLoadError(self, browser, frame, errorCode, failedUrl, errorText):
        # TODO
        print "ERROR LOADING URL : %" % failedUrl

#-------------------------------------------------------------------------------

def Initialize(settings=None):
    """Initializes CEF, We should do it before initializing wx
       If no settings passed a default is used
    """
    sys.excepthook = ExceptHook
    if not settings:
        settings = {
            "log_severity": cefpython.LOGSEVERITY_INFO,
            "log_file": GetApplicationPath("debug.log"),
            "release_dcheck_enabled": True # Enable only when debugging.
        }
    cefpython.Initialize(settings)

def Shutdown():
    """Shuts down CEF, should be called by app exiting code"""
    cefpython.Shutdown()

def ExceptHook(t, value, traceObject):
    import traceback, os, time
    # This hook does the following: in case of exception display it,
    # write to error.log, shutdown CEF and exit application.
    error = "\n".join(traceback.format_exception(t, value, traceObject))
    with open(GetApplicationPath("error.log"), "a") as f:
        f.write("\n[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), error))
    print("\n"+error+"\n")
    ##cefpython.QuitMessageLoop()
    ##cefpython.Shutdown()
    # So that "finally" does not execute.
    ##os._exit(1)