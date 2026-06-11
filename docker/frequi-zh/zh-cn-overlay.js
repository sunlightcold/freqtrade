(function () {
  "use strict";

  document.documentElement.lang = "zh-CN";

  const exactText = new Map([
    ["Trade", "交易"],
    ["Dashboard", "仪表盘"],
    ["Chart", "图表"],
    ["Logs", "日志"],
    ["Settings", "设置"],
    ["Multi Pane", "多面板"],
    ["Multi-Pane", "多面板"],
    ["Start Trading", "启动交易"],
    ["Stop Trading", "停止交易"],
    ["Reload Config", "重新加载配置"],
    ["Open Trades", "当前持仓"],
    ["No data available", "暂无数据"],
    ["Currently no open trades.", "当前没有持仓。"],
    ["Show Chart Areas", "显示图表区域"],
    ["Heikin Ashi", "平均 K 线"],
    ["Multi pair", "多币对"],
    ["default", "默认"],
    ["Filter", "筛选"],
    ["Pair", "币对"],
    ["Amount", "数量"],
    ["Stake amount", "投入金额"],
    ["Open rate", "开仓价格"],
    ["Current rate", "当前价格"],
    ["Current profit %", "当前收益 %"],
    ["Open date", "开仓时间"],
    ["Bot Name", "机器人名称"],
    ["API Url", "API 地址"],
    ["Username", "用户名"],
    ["Password", "密码"],
    ["Submit", "提交"],
    ["Reset", "重置"],
    ["Login failed", "登录失败"],
    ["Freqtrade bot Login", "Freqtrade 机器人登录"],
    ["Please verify that the bot is running, the Bot API is enabled and the URL is reachable.", "请确认机器人正在运行、Bot API 已启用，并且 API 地址可以访问。"],
    ["Total Profit", "总收益"],
    ["Total Profit %", "总收益 %"],
    ["Total profit", "总收益"],
    ["Total profit %", "总收益 %"],
    ["Avg Profit 0.000% (Σ 0.000%) in 0 Trades, with an average duration of 0:00:00. Best pair: .", "平均收益 0.000%（合计 0.000%），共 0 笔交易，平均持仓 0:00:00。最佳币对：无。"],
    ["Total Trades", "交易次数"],
    ["Total trades", "交易次数"],
    ["Avg Profit", "平均收益"],
    ["Avg profit", "平均收益"],
    ["Avg Duration", "平均持仓时间"],
    ["Avg duration", "平均持仓时间"],
    ["Best Pair", "最佳币对"],
    ["Best pair", "最佳币对"],
    ["Refresh", "刷新"],
    ["Theme", "主题"],
    ["Light", "浅色"],
    ["Dark", "深色"],
    ["System", "跟随系统"],
    ["Logout", "退出登录"],
    ["Start", "启动"],
    ["Stop", "停止"],
    ["Reload", "重新加载"],
    ["Force entry", "强制开仓"],
    ["Force exit", "强制平仓"],
    ["Cancel", "取消"],
    ["Confirm", "确认"],
    ["Save", "保存"],
    ["Close", "关闭"],
    ["Profit", "收益"],
    ["Loss", "亏损"],
    ["Result", "结果"],
    ["Date", "日期"],
    ["Rate", "价格"],
    ["Side", "方向"],
    ["Long", "做多"],
    ["Short", "做空"],
    ["Entry", "开仓"],
    ["Exit", "平仓"],
    ["Status", "状态"],
    ["Running", "运行中"],
    ["Stopped", "已停止"],
    ["Dry run", "模拟盘"],
    ["Dry-Run", "模拟盘"],
    ["Backtesting", "回测"],
    ["Live", "实盘"],
    ["Balance", "余额"],
    ["Available", "可用"],
    ["Closed Trades", "已平仓交易"],
    ["Closed trades", "已平仓交易"],
    ["Trade ID", "交易 ID"],
    ["ID", "ID"],
    ["Exchange", "交易所"],
    ["Strategy", "策略"],
    ["Timeframe", "周期"],
    ["Version", "版本"],
    ["Strategy parameters", "策略参数"],
    ["Profits for", "收益统计"],
    ["Trades", "交易"],
    ["Metric", "指标"],
    ["Value", "数值"],
    ["ROI closed trades", "已平仓交易 ROI"],
    ["ROI all trades", "全部交易 ROI"],
    ["Total Trade count", "总交易次数"],
    ["Bot started", "机器人启动时间"],
    ["First Trade opened", "第一笔交易开仓时间"],
    ["Latest Trade opened", "最近一笔交易开仓时间"],
    ["Win / Loss", "盈利 / 亏损"],
    ["Winrate", "胜率"],
    ["Expectancy (ratio)", "期望值（比率）"],
    ["CAGR", "年化复合收益率"],
    ["Calmar", "Calmar 比率"],
    ["Sharpe", "夏普比率"],
    ["Sortino", "索提诺比率"],
    ["SQN", "系统质量指数"],
    ["Avg. Duration", "平均持仓时间"],
    ["Best performing", "最佳表现"],
    ["Trading volume", "交易额"],
    ["Profit factor", "收益因子"],
    ["Max Drawdown", "最大回撤"],
    ["Current Drawdown", "当前回撤"],
    ["Open date", "开仓时间"],
    ["Close date", "平仓时间"],
    ["Close rate", "平仓价格"],
    ["Exit reason", "平仓原因"],
    ["Enter tag", "开仓标签"],
    ["Exit tag", "平仓标签"],
    ["Duration", "持仓时长"],
    ["Fee", "手续费"],
    ["Orders", "订单"],
    ["Order", "订单"],
    ["Order ID", "订单 ID"],
    ["Order date", "订单时间"],
    ["Order type", "订单类型"],
    ["Filled", "已成交"],
    ["Remaining", "剩余"],
    ["Cost", "成本"],
    ["Stake currency", "计价币种"],
    ["Stake Currency", "计价币种"],
    ["Stake amount", "投入金额"],
    ["Max open trades", "最大持仓数"],
    ["Stoploss", "止损"],
    ["Stop loss", "止损"],
    ["Trailing stop", "移动止损"],
    ["Minimal ROI", "最小 ROI"],
    ["Whitelist", "白名单"],
    ["Blacklist", "黑名单"],
    ["Pairlist", "币对列表"],
    ["Market", "市场"],
    ["Volume", "成交量"],
    ["Open", "开盘"],
    ["High", "最高"],
    ["Low", "最低"],
    ["Close price", "收盘价"],
    ["Candle", "K 线"],
    ["Candles", "K 线"],
    ["Indicators", "指标"],
    ["Chart settings", "图表设置"],
    ["Show trades", "显示交易"],
    ["Show orders", "显示订单"],
    ["Show indicators", "显示指标"],
    ["Plot Config", "绘图配置"],
    ["Bot state", "机器人状态"],
    ["Run mode", "运行模式"],
    ["Process throttle", "处理间隔"],
    ["Last update", "最后更新"],
    ["Uptime", "运行时长"],
    ["Started", "已启动"],
    ["Stopped", "已停止"],
    ["Stopping", "停止中"],
    ["Reloading", "重新加载中"],
    ["Error", "错误"],
    ["Warning", "警告"],
    ["Info", "信息"],
    ["Debug", "调试"],
    ["Log level", "日志级别"],
    ["Message", "消息"],
    ["Clear", "清空"],
    ["Download", "下载"],
    ["Auto refresh", "自动刷新"],
    ["Pagination", "分页"],
    ["Rows per page", "每页行数"],
    ["Previous", "上一页"],
    ["Next", "下一页"],
    ["First", "首页"],
    ["Last", "末页"],
    ["Search", "搜索"],
    ["Show", "显示"],
    ["Hide", "隐藏"],
    ["Add", "添加"],
    ["Edit", "编辑"],
    ["Delete", "删除"],
    ["Yes", "是"],
    ["No", "否"],
    ["Enabled", "已启用"],
    ["Disabled", "已禁用"],
    ["Connected", "已连接"],
    ["Disconnected", "未连接"],
    ["Connect", "连接"],
    ["Disconnect", "断开连接"],
    ["API URL is required.", "请填写 API 地址。"],
    ["Bot name is required.", "请填写机器人名称。"],
    ["Username is required.", "请填写用户名。"],
    ["Password is required.", "请填写密码。"],
    ["All", "全部"],
  ]);

  const attributeText = new Map([
    ["Bot Name", "机器人名称"],
    ["API Url", "API 地址"],
    ["Username", "用户名"],
    ["Password", "密码"],
    ["Filter", "筛选"],
    ["Search", "搜索"],
    ["Start Trading", "启动交易"],
    ["Stop Trading", "停止交易"],
    ["Reload Config", "重新加载配置"],
  ]);

  const replacements = [
    [/^Running Freqtrade\s+(.+)$/i, "正在运行 Freqtrade $1"],
    [/^Running with\s+(.+?)\s+on\s+(.+?)\s+in\s+(.+?)\s+markets,\s+with Strategy\s+(.+)\.$/i, "运行配置：$1，交易所：$2，市场模式：$3，策略：$4。"],
    [/^Stoploss on exchange is\s+(.+)\.$/i, "交易所止损：$1。"],
    [/^Currently\s+(.+?),\s+force entry:\s+(.+)$/i, "当前状态：$1，强制开仓：$2"],
    [/^Avg Profit\s+(.+?)\s+\(Σ\s+(.+?)\)\s+in\s+(\d+)\s+Trades,\s+with an average duration of\s+(.+?)\.\s+Best pair:\s*(.*)$/i, "平均收益 $1（合计 $2），共 $3 笔交易，平均持仓 $4。最佳币对：$5"],
    [/^Long entries:\s*(\d+)\s+Long exit:\s*(\d+)$/i, "多头开仓：$1 多头平仓：$2"],
    [/^Short entries:\s*(\d+)\s+Short exit:\s*(\d+)$/i, "空头开仓：$1 空头平仓：$2"],
    [/^You can verify this by navigating to (.+) to make sure the bot API is reachable\.?$/i, "你可以打开 $1 来确认 Bot API 是否可访问。"],
    [/^API URL is required\.?$/i, "请填写 API 地址。"],
    [/^No trades found\.?$/i, "没有找到交易。"],
    [/^Showing\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)\s+entries$/i, "显示第 $1 到 $2 条，共 $3 条"],
    [/^Page\s+(\d+)\s+of\s+(\d+)$/i, "第 $1 页，共 $2 页"],
    [/^(.+)\s+is required\.?$/i, "$1 为必填项。"],
  ];

  const ignoredTags = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "CODE", "PRE", "TEXTAREA"]);

  function preserveWhitespace(original, translated) {
    const leading = original.match(/^\s*/)?.[0] ?? "";
    const trailing = original.match(/\s*$/)?.[0] ?? "";
    return `${leading}${translated}${trailing}`;
  }

  function translateString(value) {
    const trimmed = value.trim();
    if (!trimmed) {
      return value;
    }

    const normalized = trimmed.replace(/\s+/g, " ");
    if (exactText.has(trimmed)) {
      return preserveWhitespace(value, exactText.get(trimmed));
    }
    if (exactText.has(normalized)) {
      return preserveWhitespace(value, exactText.get(normalized));
    }

    for (const [pattern, replacement] of replacements) {
      if (pattern.test(trimmed)) {
        return preserveWhitespace(value, trimmed.replace(pattern, replacement));
      }
      if (pattern.test(normalized)) {
        return preserveWhitespace(value, normalized.replace(pattern, replacement));
      }
    }

    return value;
  }

  function translateAttributes(element) {
    for (const attr of ["placeholder", "title", "aria-label", "alt"]) {
      const value = element.getAttribute(attr);
      if (!value) {
        continue;
      }
      const trimmed = value.trim();
      const translated = attributeText.get(trimmed) ?? exactText.get(trimmed);
      if (translated) {
        element.setAttribute(attr, preserveWhitespace(value, translated));
      }
    }
  }

  function translateNode(root) {
    if (!root) {
      return;
    }

    if (root.nodeType === Node.ELEMENT_NODE) {
      const element = root;
      if (ignoredTags.has(element.tagName)) {
        return;
      }
      translateAttributes(element);
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
      acceptNode(node) {
        if (node.nodeType === Node.ELEMENT_NODE && ignoredTags.has(node.tagName)) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    let node = root.nodeType === Node.TEXT_NODE ? root : walker.nextNode();
    while (node) {
      if (node.nodeType === Node.TEXT_NODE) {
        const translated = translateString(node.nodeValue ?? "");
        if (translated !== node.nodeValue) {
          node.nodeValue = translated;
        }
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        translateAttributes(node);
      }
      node = walker.nextNode();
    }
  }

  let pending = false;
  function scheduleTranslate() {
    if (pending) {
      return;
    }
    pending = true;
    window.requestAnimationFrame(() => {
      pending = false;
      translateNode(document.body);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleTranslate, { once: true });
  } else {
    scheduleTranslate();
  }

  const observer = new MutationObserver(scheduleTranslate);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["placeholder", "title", "aria-label", "alt"],
  });
})();
