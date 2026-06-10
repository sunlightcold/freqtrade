(function () {
  "use strict";

  document.documentElement.lang = "zh-CN";

  const exactText = new Map([
    ["Trade", "交易"],
    ["Dashboard", "仪表盘"],
    ["Chart", "图表"],
    ["Logs", "日志"],
    ["Multi Pane", "多面板"],
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
    ["Open Trades", "当前持仓"],
    ["Total Profit", "总收益"],
    ["Total Profit %", "总收益 %"],
    ["Total Trades", "交易次数"],
    ["Avg Profit", "平均收益"],
    ["Avg Duration", "平均持仓时间"],
    ["Best Pair", "最佳币对"],
    ["Refresh", "刷新"],
    ["Settings", "设置"],
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
    ["Backtesting", "回测"],
    ["Balance", "余额"],
    ["Available", "可用"],
    ["Closed Trades", "已平仓交易"],
    ["Trade ID", "交易 ID"],
    ["Exchange", "交易所"],
    ["Strategy", "策略"],
    ["Timeframe", "周期"],
    ["Version", "版本"],
  ]);

  const attributeText = new Map([
    ["Bot Name", "机器人名称"],
    ["API Url", "API 地址"],
    ["Username", "用户名"],
    ["Password", "密码"],
    ["Filter", "筛选"],
    ["Search", "搜索"],
  ]);

  const replacements = [
    [/^Long entries:\s*(\d+)\s+Long exit:\s*(\d+)$/i, "多头开仓：$1 多头平仓：$2"],
    [/^Short entries:\s*(\d+)\s+Short exit:\s*(\d+)$/i, "空头开仓：$1 空头平仓：$2"],
    [/^You can verify this by navigating to (.+) to make sure the bot API is reachable\.?$/i, "你可以打开 $1 来确认 Bot API 是否可访问。"],
    [/^API URL is required\.?$/i, "请填写 API 地址。"],
    [/^No trades found\.?$/i, "没有找到交易。"],
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

    if (exactText.has(trimmed)) {
      return preserveWhitespace(value, exactText.get(trimmed));
    }

    for (const [pattern, replacement] of replacements) {
      if (pattern.test(trimmed)) {
        return preserveWhitespace(value, trimmed.replace(pattern, replacement));
      }
    }

    return value;
  }

  function translateAttributes(element) {
    for (const attr of ["placeholder", "title", "aria-label", "alt"]) {
      const value = element.getAttribute(attr);
      if (value && attributeText.has(value.trim())) {
        element.setAttribute(attr, preserveWhitespace(value, attributeText.get(value.trim())));
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
