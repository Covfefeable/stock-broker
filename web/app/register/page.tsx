"use client";

import { FundProjectionScreenOutlined, LockOutlined, MailOutlined, UserOutlined } from "@ant-design/icons";
import { Button, Form, Input, Typography, message } from "antd";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthThemeToggle } from "@/components/auth-theme-toggle";
import { setAccessToken } from "@/lib/auth";
import { apiPost } from "@/lib/api";

const { Text, Title } = Typography;

type RegisterResponse = {
  access_token: string;
};

export default function RegisterPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [messageApi, contextHolder] = message.useMessage();

  const handleSubmit = async (values: {
    email: string;
    username: string;
    password: string;
    confirmPassword: string;
  }) => {
    if (values.password !== values.confirmPassword) {
      messageApi.error("两次输入的密码不一致。");
      return;
    }

    try {
      const response = await apiPost<RegisterResponse>("/auth/register", {
        email: values.email,
        username: values.username,
        password: values.password,
      });
      setAccessToken(response.access_token);
      router.replace(searchParams.get("next") || "/");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "注册失败。");
    }
  };

  return (
    <main className="login-page">
      {contextHolder}
      <AuthThemeToggle />
      <section className="login-hero">
        <div className="login-brand">
          <span className="login-brand-mark">
            <FundProjectionScreenOutlined />
          </span>
          <div>
            <strong>Genesis</strong>
            <Text>AI 量化策略平台</Text>
          </div>
        </div>

        <div className="login-copy">
          <div>
            <Title>创建账号</Title>
            <Text>注册后即可进入平台，开始管理多市场数据、策略和 AI Agent 任务。</Text>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-panel-head">
          <Title level={2}>注册</Title>
          <Text>创建一个新账号以继续使用平台。</Text>
        </div>

        <Form layout="vertical" requiredMark={false} onFinish={handleSubmit}>
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input prefix={<UserOutlined />} placeholder="请输入用户名" size="large" />
          </Form.Item>
          <Form.Item label="邮箱" name="email" rules={[{ required: true, message: "请输入邮箱" }]}>
            <Input prefix={<MailOutlined />} placeholder="请输入邮箱" size="large" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="至少 8 位密码" size="large" />
          </Form.Item>
          <Form.Item
            label="确认密码"
            name="confirmPassword"
            rules={[{ required: true, message: "请再次输入密码" }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请再次输入密码" size="large" />
          </Form.Item>
          <Button block type="primary" htmlType="submit" size="large">
            注册
          </Button>
          <div className="login-footer-link">
            <Text>已有账号？</Text>
            <Link href="/login">返回登录</Link>
          </div>
        </Form>
      </section>
    </main>
  );
}
