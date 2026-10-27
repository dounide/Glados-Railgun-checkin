"""Offline regression tests: no credentials, live check-ins, or push messages."""
import json
import logging
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import checkin as app

COOKIE = "koa:sess=fake; koa:sess.sig=fake; gld:sess=fake; gld:sess.sig=fake"


def response(body, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(body).encode()
    return result


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GLADOS_COOKIES": COOKIE}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        network = patch.object(requests.Session, "request", side_effect=AssertionError("Live network is forbidden"))
        network.start()
        self.addCleanup(network.stop)
        push = patch.object(app.PushDeer, "send_text", side_effect=AssertionError("Live push is forbidden"))
        push.start()
        self.addCleanup(push.stop)

    def api(self, domain="glados.cloud"):
        api = app.API(domain)
        self.addCleanup(api.close)
        return api

    def test_success_and_repeat(self):
        for code, expected in [(0, app.CheckinStatus.SUCCESS), (1, app.CheckinStatus.REPEAT)]:
            with self.subTest(code=code):
                api = self.api()
                with patch.object(api, "_make_request", return_value=response({"code": code, "points": 7})) as request:
                    result = api.checkin(COOKIE)
                self.assertEqual(result["code"], expected)
                self.assertEqual(result["points"], "7" if code == 0 else "0")
                request.assert_called_once()

    def test_known_device_retry_and_followup_headers(self):
        for platform in ("macOS", "Linux", "iPhone", "Android"):
            with self.subTest(platform=platform):
                api = self.api()
                mismatch = {"code": 4, "reason": "device-mismatch", "loginDevice": platform}
                with patch.object(api, "_make_request", side_effect=[response(mismatch), response({"code": 0})]) as request:
                    result = api.checkin(COOKIE)
                self.assertEqual(result["code"], app.CheckinStatus.SUCCESS)
                self.assertEqual(request.call_count, 2)
                self.assertEqual(request.call_args.kwargs["user_agent"], app.PLATFORM_UA[platform])
                self.assertEqual(api.session.headers["user-agent"], app.PLATFORM_UA[platform])
                self.assertEqual(api.headers["user-agent"], app.PLATFORM_UA[platform])

    def test_no_unbounded_device_retry(self):
        api = self.api()
        mismatch = {"code": 4, "reason": "device-mismatch", "loginDevice": "macOS"}
        with patch.object(api, "_make_request", return_value=response(mismatch)) as request:
            result = api.checkin(COOKIE)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result["code"], app.CheckinStatus.FAILURE)
        self.assertIn("device-mismatch", result["message"])

    def test_unknown_same_or_malformed_device_is_not_retried(self):
        for device in ("Unknown", "Windows", None, {"bad": "device"}):
            with self.subTest(device=device):
                api = self.api()
                with patch.object(api, "_make_request", return_value=response({"code": 4, "reason": "device-mismatch", "loginDevice": device})) as request:
                    result = api.checkin(COOKIE)
                request.assert_called_once()
                self.assertEqual(result["code"], app.CheckinStatus.FAILURE)

    def test_actual_permission_errors_recommend_refresh_without_retry(self):
        for message in ("没有权限", "No permission"):
            with self.subTest(message=message):
                api = self.api()
                with patch.object(api, "_make_request", return_value=response({"code": -2, "message": message})) as request:
                    result = api.checkin(COOKIE)
                request.assert_called_once()
                self.assertEqual(result["code"], app.CheckinStatus.FAILURE)
                self.assertIn("鉴权被拒绝", result["message"])
                self.assertIn("完整 Cookie", result["message"])

    def test_other_business_errors_are_not_retried(self):
        api = self.api()
        with patch.object(api, "_make_request", return_value=response({"code": 4, "reason": "other", "loginDevice": "macOS"})) as request:
            result = api.checkin(COOKIE)
        request.assert_called_once()
        self.assertIn("reason=other", result["message"])

    def test_invalid_json_and_non_object_json(self):
        for body in ([], None, "unexpected", {}):
            with self.subTest(body=body):
                api = self.api()
                with patch.object(api, "_make_request", return_value=response(body)):
                    self.assertEqual(api.checkin(COOKIE)["code"], app.CheckinStatus.FAILURE)
        api = self.api()
        html = response({})
        html._content = b"<html>Login</html>"
        with patch.object(api, "_make_request", return_value=html):
            self.assertIn("JSON", api.checkin(COOKIE)["message"])

    def test_http_error_preserves_status_but_not_response_body(self):
        api = self.api()
        with patch.object(api.session, "post", return_value=response("PRIVATE_BODY", 403)):
            with self.assertLogs(level="WARNING") as logs:
                result = api.checkin(COOKIE)
        self.assertIn("HTTP 403", result["message"])
        self.assertNotIn("PRIVATE_BODY", " ".join(logs.output))
        self.assertNotIn(COOKIE, " ".join(logs.output))

    def test_timeout_has_failure_code(self):
        api = self.api()
        with patch.object(api.session, "post", side_effect=requests.Timeout("timeout")):
            result = api.checkin(COOKIE)
        self.assertEqual(result["code"], app.CheckinStatus.FAILURE)
        self.assertIn("Timeout", result["message"])

    def test_adapter_does_not_replay_post_status_errors(self):
        retry = self.api().session.get_adapter("https://glados.cloud").max_retries
        self.assertTrue(retry.is_retry("GET", 503))
        self.assertFalse(retry.is_retry("POST", 503))
        self.assertFalse(retry.is_retry("POST", 429))

    def test_cookie_warning_contains_names_not_values(self):
        with patch.dict(os.environ, {"GLADOS_COOKIES": "koa:sess=PRIVATE_VALUE; koa:sess.sig=PRIVATE_SIG"}):
            with self.assertLogs(level="WARNING") as logs:
                config = app.Config()
        text = " ".join(logs.output)
        self.assertIn("gld:sess", text)
        self.assertNotIn("PRIVATE_VALUE", text)
        self.assertNotIn("PRIVATE_SIG", text)
        self.assertEqual(len(config.cookies_list), 1)

    def test_default_and_blank_domains_use_logged_in_site(self):
        self.assertEqual(app.Config().DOMAINS, ["glados.space"])
        for value in ("", " \t "):
            with self.subTest(value=value), patch.dict(os.environ, {"GLADOS_DOMAINS": value}):
                self.assertEqual(app.Config().DOMAINS, ["glados.space"])

    def test_explicit_domains_are_unique_and_do_not_change_other_instances(self):
        with patch.dict(os.environ, {
            "GLADOS_DOMAINS": " RAILGUN.INFO, glados.cloud,RAILGUN.INFO,,GLADOS.SPACE "
        }):
            selected = app.Config()
        self.assertEqual(selected.DOMAINS, ["railgun.info", "glados.cloud", "glados.space"])
        default = app.Config()
        selected.DOMAINS.clear()
        default.DOMAINS.append("railgun.info")
        self.assertEqual(app.Config().DOMAINS, ["glados.space"])

    def test_invalid_domain_fails_before_constructing_a_checker(self):
        for value in (
            ", ,", "https://glados.space", "glados.space/console/checkin",
            "glados.space.evil.example", "evil.example/glados.space",
            "glados.space:443", "user@glados.space", "glados.space,evil.example",
            "glados.space?cookie=PRIVATE_VALUE", "glados.space\nrailgun.info",
        ):
            with self.subTest(value=value), patch.dict(os.environ, {"GLADOS_DOMAINS": value}):
                with patch.object(app, "Checker") as factory, patch.object(app, "PushService") as push:
                    with self.assertLogs(level="ERROR") as logs:
                        self.assertEqual(app.main(), 1)
                    factory.assert_not_called()
                    push.assert_not_called()
                    self.assertNotIn("PRIVATE_VALUE", " ".join(logs.output))

    def test_selected_domain_controls_request_and_does_not_fall_back(self):
        for domain in ("glados.space", "glados.cloud", "railgun.info"):
            for code, expected in ((0, app.CheckinStatus.SUCCESS), (-2, app.CheckinStatus.FAILURE)):
                with self.subTest(domain=domain, code=code), patch.dict(os.environ, {"GLADOS_DOMAINS": domain}):
                    config = app.Config()
                    reads = [response({"code": 0, "data": {"leftDays": 14}}),
                             response({"code": 0, "points": 71})]
                    body = {"code": code, "points": 5, "message": "ok" if code == 0 else "No permission"}
                    with patch.object(requests.Session, "get", side_effect=reads) as get:
                        with patch.object(requests.Session, "post", return_value=response(body)) as post:
                            checker = app.Checker(config)
                            checker.checkin_all()
                    post.assert_called_once()
                    self.assertEqual(post.call_args.args, (f"https://{domain}/api/user/checkin",))
                    self.assertEqual(post.call_args.kwargs["data"], {"token": domain})
                    self.assertEqual(post.call_args.kwargs["headers"]["origin"], f"https://{domain}")
                    self.assertEqual(post.call_args.kwargs["headers"]["cookie"], COOKIE)
                    self.assertEqual([call.args[0] for call in get.call_args_list], [
                        f"https://{domain}/api/user/status", f"https://{domain}/api/user/points"
                    ])
                    self.assertEqual(len(checker.results), 1)
                    self.assertEqual(checker.results[0].code, expected)
                    self.assertEqual(checker.results[0].domain, domain)

    def test_authentication_hint_identifies_the_cookie_source_domain(self):
        for domain in ("glados.space", "glados.cloud", "railgun.info"):
            with self.subTest(domain=domain):
                api = self.api(domain)
                with patch.object(api, "_make_request", return_value=response({"code": -2, "message": "No permission"})):
                    result = api.checkin(COOKIE)
                self.assertIn(f"https://{domain}/console/checkin", result["message"])
                self.assertIn("GLADOS_DOMAINS", result["message"])
                self.assertNotIn(COOKIE, result["message"])

    def test_default_exchange_disabled_and_explicit_plan_preserved(self):
        self.assertEqual(app.Config().exchange_plan, "none")
        with patch.dict(os.environ, {"GLADOS_EXCHANGE_PLAN": "plan200"}):
            self.assertEqual(app.Config().exchange_plan, "plan200")

    def test_checker_carries_points_and_reason_and_skips_exchange(self):
        for status in (app.CheckinStatus.SUCCESS, app.CheckinStatus.FAILURE):
            with self.subTest(status=status):
                config = app.Config()
                if status == app.CheckinStatus.FAILURE:
                    config.exchange_plan = "plan100"
                with patch.object(app, "API") as factory:
                    api = factory.return_value.__enter__.return_value
                    api.get_status.return_value = ("10 天", 0)
                    api.get_points.return_value = ("1000 积分", 1000)
                    api.checkin.return_value = {"status": "result", "code": status, "points": "7", "message": "diagnostic"}
                    checker = app.Checker(config)
                    result = checker._checkin_on_domain(COOKIE, 1, "glados.cloud")
                    api.exchange.assert_not_called()
                self.assertEqual(result.points, "7")
                self.assertEqual(result.message, "diagnostic")
                checker.results = [result]
                if status == app.CheckinStatus.FAILURE:
                    _, push, log = checker.format_results()
                    self.assertIn("diagnostic", push)
                    self.assertIn("diagnostic", log)

    def test_success_with_explicit_exchange_plan(self):
        config = app.Config()
        config.exchange_plan = "plan100"
        with patch.object(app, "API") as factory:
            api = factory.return_value.__enter__.return_value
            api.get_status.return_value = ("10 天", 0)
            api.get_points.return_value = ("1000 积分", 1000)
            api.checkin.return_value = {"status": "成功", "code": app.CheckinStatus.SUCCESS}
            app.Checker(config)._checkin_on_domain(COOKIE, 1, "glados.cloud")
            api.exchange.assert_called_once_with(COOKIE, "plan100", 100)

    def test_exchange_balance_threshold_and_failed_points_query(self):
        for plan, required in (("plan100", 100), ("plan200", 200), ("plan500", 500)):
            for status in (app.CheckinStatus.SUCCESS, app.CheckinStatus.REPEAT):
                for balance in (0, required - 1, required):
                    with self.subTest(plan=plan, status=status, balance=balance):
                        config = app.Config()
                        config.exchange_plan = plan
                        with patch.object(app, "API") as factory:
                            api = factory.return_value.__enter__.return_value
                            api.get_status.return_value = ("14 天", 0)
                            api.get_points.return_value = ("None 积分" if balance == 0 else f"{balance} 积分", balance)
                            api.checkin.return_value = {"status": "result", "code": status, "points": "5"}
                            result = app.Checker(config)._checkin_on_domain(COOKIE, 1, "glados.space")
                            if balance < required:
                                api.exchange.assert_not_called()
                                self.assertIn("跳过自动兑换", result.exchange)
                            else:
                                api.exchange.assert_called_once_with(COOKIE, plan, required)
                            self.assertEqual(result.code, status)

    def test_default_success_log_includes_awarded_points_without_cookie(self):
        config = app.Config()
        self.assertFalse(config.verbose)
        checker = app.Checker(config)
        result = app.CheckinResult(1, "glados.space", status="签到成功", points="7", code=app.CheckinStatus.SUCCESS)
        with patch.object(checker, "_checkin_on_domain", return_value=result):
            with self.assertLogs(level="INFO") as logs:
                checker.checkin_all()
        output = " ".join(logs.output)
        self.assertIn("获得 7 积分", output)
        self.assertNotIn(COOKIE, output)

    def test_main_exit_codes(self):
        scenarios = [([], 1), ([app.CheckinStatus.SUCCESS], 0), ([app.CheckinStatus.REPEAT], 0),
                     ([app.CheckinStatus.SUCCESS, app.CheckinStatus.FAILURE], 1)]
        for statuses, expected in scenarios:
            with self.subTest(statuses=statuses), patch.object(app, "Checker") as factory, patch.object(app, "PushService") as push:
                checker = factory.return_value
                checker.results = [app.CheckinResult(1, "glados.cloud", code=s) for s in statuses]
                checker.format_results.return_value = ("title", "content", "log")
                self.assertEqual(app.main(), expected)
                push.return_value.send.assert_called_once()

    def test_format_error_after_success_still_returns_failure(self):
        with patch.object(app, "Checker") as factory, patch.object(app, "PushService"):
            checker = factory.return_value
            checker.results = [app.CheckinResult(1, "glados.cloud", code=app.CheckinStatus.SUCCESS)]
            checker.format_results.side_effect = ValueError("format error")
            self.assertEqual(app.main(), 1)

    def test_no_cookie_or_config_exception_returns_failure(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(app.main(), 1)
        with patch.object(app, "Config", side_effect=ValueError("bad config")):
            self.assertEqual(app.main(), 1)

    def test_workflow_keeps_schedule_and_correct_branch(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/gladosCheck.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [ master ]", text)
        self.assertIn("cron: '0 4,10 * * *'", text)
        self.assertIn("unittest discover -s tests -v", text)

    def test_beijing_logging_timezone(self):
        record = logging.LogRecord("test", logging.INFO, "", 0, "message", (), None)
        record.created = 0
        self.assertEqual(logging.Formatter().formatTime(record, "%Y-%m-%d %H:%M:%S"), "1970-01-01 08:00:00")


if __name__ == "__main__":
    unittest.main()
