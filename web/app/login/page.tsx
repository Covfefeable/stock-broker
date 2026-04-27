"use client";

import { LockOutlined, MailOutlined } from "@ant-design/icons";
import { Button, Checkbox, Form, Input, Typography, message } from "antd";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthThemeToggle } from "@/components/auth-theme-toggle";
import { setAccessToken } from "@/lib/auth";
import { apiPost } from "@/lib/api";

const { Text, Title } = Typography;

type LoginResponse = {
  access_token: string;
};

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [messageApi, contextHolder] = message.useMessage();

  const handleSubmit = async (values: { email: string; password: string }) => {
    try {
      const response = await apiPost<LoginResponse>("/auth/login", values);
      setAccessToken(response.access_token);
      router.replace(searchParams.get("next") || "/");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "登录失败。");
    }
  };

  return (
    <main className="login-page">
      {contextHolder}
      <AuthThemeToggle />
      <section className="login-hero">
        <div className="login-brand">
          <span className="login-brand-mark">
            <img src="/brand-logo.svg" alt="" />
          </span>
          <div>
            <strong>Genesis</strong>
            <Text>AI 量化策略平台</Text>
          </div>
        </div>

        <div className="login-copy">
          <div>
            <Title>进入策略工作台</Title>
            <Text>
              管理多市场行情数据、构建规则策略、运行回测，并让 AI Agent 持续探索更稳健的策略假设。
            </Text>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-panel-head">
          <Title level={2}>登录</Title>
          <Text>使用你的账号继续访问平台。</Text>
        </div>

        <Form layout="vertical" requiredMark={false} onFinish={handleSubmit}>
          <Form.Item label="邮箱" name="email" rules={[{ required: true, message: "请输入邮箱" }]}>
            <Input prefix={<MailOutlined />} placeholder="请输入邮箱" size="large" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" size="large" />
          </Form.Item>
          <div className="login-form-row">
            <Checkbox>保持登录状态</Checkbox>
            <Button type="link">忘记密码</Button>
          </div>
          <Button block type="primary" size="large" htmlType="submit">
            登录
          </Button>
          <div className="login-footer-link">
            <Text>还没有账号？</Text>
            <Link href="/register">立即注册</Link>
          </div>
        </Form>
      </section>
    </main>
  );
}
