#!/bin/bash

# BotForge Deployment Script
# استخدم هذا السكريبت لنشر البوت على خادم Linux

echo "🚀 بدء نشر BotForge..."

# التحقق من Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 غير مثبت. قم بتثبيته أولاً."
    exit 1
fi

# تثبيت المتطلبات
echo "📦 تثبيت المتطلبات..."
pip3 install -r requirements.txt

# التحقق من ملف .env
if [ ! -f .env ]; then
    echo "⚠️  ملف .env غير موجود!"
    echo "انسخ .env.example إلى .env وأضف توكن البوت ومعرف المالك"
    exit 1
fi

# إنشاء المجلدات المطلوبة
echo "📁 إنشاء المجلدات..."
mkdir -p hosted_bots botforge_logs data .tmp

# تشغيل البوت
echo "🤖 تشغيل BotForge..."
python3 main.py