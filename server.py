#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""飞书招聘候选人信息查询 REST API"""
import os, re, time, logging, requests
from flask import Flask, request, jsonify
from flask_cors import CORS

APP_ID = "cli_aaf46add68399bb7"
APP_SECRET = "3HtvVNTWUhgGkNnBLVYumbxY7AKwEcm6"
PORT = int(os.environ.get("PORT", 8765))
FEISHU_BASE = "https://open.feishu.cn/open-apis"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("feishu-hire")

app = Flask(__name__)
CORS(app)

_token_cache = {"token": None, "expire": 0}

def get_token():
    now = time.time()
    if _token_cache["token"] and _token_cache["expire"] > now + 60:
        return _token_cache["token"]
    url = f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
    data = resp.json()
    if data.get("code") == 0:
        _token_cache["token"] = data["tenant_access_token"]
        _token_cache["expire"] = now + data.get("expire", 7200)
        logger.info("token获取成功")
        return _token_cache["token"]
    raise Exception(f"获取token失败: {data.get('msg')}")

def headers():
    return {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}

def get_candidate(talent_id):
    try:
        url = f"{FEISHU_BASE}/hire/v1/talents/{talent_id}"
        resp = requests.get(url, headers=headers(), timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            return data.get("data", {}).get("talent", {})
        logger.error(f"获取候选人失败: {data.get('msg')}")
        return None
    except Exception as e:
        logger.error(f"获取候选人异常: {e}")
        return None

def get_application_detail(app_id):
    try:
        url = f"{FEISHU_BASE}/hire/v1/applications/{app_id}"
        resp = requests.get(url, headers=headers(), timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            return data.get("data", {}).get("application", {})
        logger.error(f"获取投递详情失败: {data.get('msg')}")
        return None
    except Exception as e:
        logger.error(f"获取投递详情异常: {e}")
        return None

def get_applications(talent_id):
    try:
        url = f"{FEISHU_BASE}/hire/v1/applications"
        resp = requests.get(url, headers=headers(), params={"talent_id": talent_id, "page_size": 50}, timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            app_ids = data.get("data", {}).get("items", [])
            details = []
            for app_id in app_ids:
                detail = get_application_detail(app_id)
                if detail:
                    details.append(detail)
            return details
        logger.error(f"获取投递记录失败: {data.get('msg')}")
        return []
    except Exception as e:
        logger.error(f"获取投递记录异常: {e}")
        return []

def get_job(job_id):
    try:
        url = f"{FEISHU_BASE}/hire/v1/jobs/{job_id}"
        resp = requests.get(url, headers=headers(), timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            return data.get("data", {}).get("job", {})
        logger.error(f"获取职位失败: {data.get('msg')}")
        return None
    except Exception as e:
        logger.error(f"获取职位异常: {e}")
        return None

def get_interviews(application_id):
    try:
        url = f"{FEISHU_BASE}/hire/v1/interviews"
        resp = requests.get(url, headers=headers(), params={"application_id": application_id, "page_size": 50}, timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            items = data.get("data", {}).get("items", [])
            return items[:10]
        logger.error(f"获取面试记录失败: {data.get('msg')}")
        return []
    except Exception as e:
        logger.error(f"获取面试记录异常: {e}")
        return []

def get_round(stage):
    if not stage: return "未知"
    s = str(stage)
    if "初面" in s or "一面" in s: return "初面"
    if "复面" in s or "二面" in s or "综合面试" in s: return "复面"
    if "终面" in s or "三面" in s or "HR面" in s: return "终面"
    return "初面"

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "v1.3.0"})

@app.route("/resume", methods=["POST"])
def resume():
    try:
        data = request.get_json()
        url = data.get("url", "")
        logger.info(f"解析简历链接: {url}")
        
        talent_match = re.search(r'/talent/(\d+)', url)
        app_match = re.search(r'application_id=(\d+)', url)
        talent_id = talent_match.group(1) if talent_match else None
        application_id = app_match.group(1) if app_match else None
        
        if not talent_id:
            return jsonify({"success": False, "error": "无法解析简历链接"}), 400
        
        candidate = get_candidate(talent_id)
        if not candidate:
            return jsonify({"success": False, "error": "获取候选人信息失败"}), 500
        
        applications = get_applications(talent_id)
        target_app = None
        if application_id:
            for app in applications:
                if str(app.get("id")) == str(application_id):
                    target_app = app
                    break
        if not target_app and applications:
            target_app = applications[0]
        
        job = None
        interviews = []
        current_round = "未知"
        if target_app:
            job_id = target_app.get("job_id") or target_app.get("job", {}).get("id")
            app_id = target_app.get("id") or application_id
            if job_id:
                job = get_job(job_id)
            if app_id:
                interviews = get_interviews(app_id)
            stage_obj = target_app.get("stage") or {}
            stage_name = stage_obj.get("zh_name", "") if isinstance(stage_obj, dict) else str(stage_obj)
            current_round = get_round(stage_name)
        
        result = {
            "candidate": candidate,
            "applications": applications,
            "target_application": target_app,
            "job": job,
            "interviews": interviews,
            "current_round": current_round,
            "candidate_name": candidate.get("basic_info", {}).get("name", "未知"),
            "summary": f"候选人={candidate.get('basic_info', {}).get('name', '未知')}, 投递数={len(applications)}, 面评数={len(interviews)}, 当前轮次={current_round}"
        }
        logger.info(f"解析完成: {result['summary']}")
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"异常: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("飞书招聘候选人信息查询服务启动")
    logger.info(f"端口: {PORT}")
    logger.info("=" * 50)
    app.run(host="0.0.0.0", port=PORT, debug=False)
