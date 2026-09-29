#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from icalendar import Calendar
import pytz
import numpy as np
from collections import defaultdict
import matplotlib.dates as mdates

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # macOS
plt.rcParams['axes.unicode_minus'] = False
plt.style.use('seaborn-v0_8')

def load_calendar_data(ics_path):
    """加载并解析ICS文件"""
    with open(ics_path, 'rb') as f:
        cal = Calendar.from_ical(f.read())

    events = []
    for component in cal.walk():
        if component.name == "VEVENT":
            start = component.get('dtstart').dt
            end = component.get('dtend').dt
            summary = str(component.get('summary'))
            created = component.get('created').dt if component.get('created') else start

            # 确保时间是datetime对象
            if isinstance(start, datetime) and isinstance(end, datetime):
                duration = (end - start).total_seconds() / 3600  # 转换为小时
                events.append({
                    'summary': summary,
                    'start': pd.to_datetime(start),
                    'end': pd.to_datetime(end),
                    'duration': duration,
                    'created': pd.to_datetime(created),
                    'date': pd.to_datetime(start.date())
                })

    return pd.DataFrame(events)

def analyze_time_distribution(df):
    """分析时间分配情况"""
    # 按日期统计
    daily_stats = df.groupby('date').agg({
        'duration': ['sum', 'count'],
        'summary': list
    }).reset_index()

    # 按周统计
    df['week'] = df['date'].dt.strftime('%Y-W%W')
    weekly_stats = df.groupby('week').agg({
        'duration': ['sum', 'count'],
        'summary': list
    }).reset_index()

    # 按月统计
    df['month'] = df['date'].dt.strftime('%Y-%m')
    monthly_stats = df.groupby('month').agg({
        'duration': ['sum', 'count'],
        'summary': list
    }).reset_index()

    return daily_stats, weekly_stats, monthly_stats

def plot_time_series(df, output_dir):
    """绘制时间序列图表"""
    plt.figure(figsize=(15, 8))

    # 日活动时长趋势
    plt.subplot(2, 1, 1)
    sns.scatterplot(data=df, x='date', y='duration', alpha=0.6)
    plt.plot(df['date'], df['duration'].rolling(window=7).mean(), color='red', label='7日移动平均')
    plt.title('每日活动时长趋势')
    plt.xlabel('日期')
    plt.ylabel('时长（小时）')
    plt.legend()

    # 活动频率热力图
    plt.subplot(2, 1, 2)
    df['week_num'] = df['date'].dt.isocalendar().week
    df['weekday'] = df['date'].dt.weekday
    activity_matrix = pd.pivot_table(
        df,
        values='duration',
        index='week_num',
        columns='weekday',
        aggfunc='sum'
    )
    sns.heatmap(activity_matrix, cmap='YlOrRd', cbar_kws={'label': '活动时长（小时）'})
    plt.title('活动频率热力图')
    plt.xlabel('星期')
    plt.ylabel('周数')

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'time_series_analysis.png'))
    plt.close()

def detect_anomalies(df):
    """检测异常活动"""
    # 计算时长的统计特征
    mean_duration = df['duration'].mean()
    std_duration = df['duration'].std()

    # 定义异常阈值（超过2个标准差）
    anomalies = df[abs(df['duration'] - mean_duration) > 2 * std_duration]
    return anomalies

def generate_report(df, daily_stats, weekly_stats, monthly_stats, anomalies, output_dir):
    """生成分析报告"""
    report = []
    report.append("# 时间分配分析报告\n")

    # 数据概览
    report.append("## 1. 数据概览\n")
    report.append(f"- 分析周期：{df['date'].min().strftime('%Y-%m-%d')} 至 {df['date'].max().strftime('%Y-%m-%d')}")
    report.append(f"- 总记录数：{len(df)} 条")
    report.append(f"- 总活动时长：{df['duration'].sum():.1f} 小时")
    report.append(f"- 平均每日活动时长：{df['duration'].mean():.1f} 小时")

    # 时间分配趋势
    report.append("\n## 2. 时间分配趋势\n")
    report.append("### 2.1 月度趋势")
    monthly_summary = monthly_stats.to_string()
    report.append(f"```\n{monthly_summary}\n```")

    report.append("\n### 2.2 周度趋势")
    weekly_summary = weekly_stats.to_string()
    report.append(f"```\n{weekly_summary}\n```")

    # 异常分析
    report.append("\n## 3. 异常活动分析\n")
    if not anomalies.empty:
        report.append("检测到以下异常活动：")
        for _, row in anomalies.iterrows():
            report.append(f"- {row['date'].strftime('%Y-%m-%d')}: {row['summary']} (时长: {row['duration']:.1f}小时)")
    else:
        report.append("未检测到显著异常活动。")

    # 输出报告
    with open(os.path.join(output_dir, 'calendar_analysis_report.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

def main():
    parser = argparse.ArgumentParser(description="分析日历 .ics 导出文件的时间分配情况")
    parser.add_argument("--ics", default="sample.ics", help="日历 .ics 文件路径（默认用仓库自带的 sample.ics 示例）")
    parser.add_argument("--output", default="analysis_output", help="报告和图表的输出目录")
    args = parser.parse_args()

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    # 加载数据
    df = load_calendar_data(args.ics)

    # 数据分析
    daily_stats, weekly_stats, monthly_stats = analyze_time_distribution(df)

    # 绘制图表
    plot_time_series(df, args.output)

    # 异常检测
    anomalies = detect_anomalies(df)

    # 生成报告
    generate_report(df, daily_stats, weekly_stats, monthly_stats, anomalies, args.output)

    print(f"分析完成，报告和图表在 {args.output}/ 下。")

if __name__ == "__main__":
    main()
