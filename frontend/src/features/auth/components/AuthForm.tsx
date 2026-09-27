"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError } from "@/services/api-client";

interface AuthFormProps {
  mode: "login" | "register";
}

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const { login, register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const isRegister = mode === "register";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      if (isRegister) await register(email, password);
      else await login(email, password);
      router.push("/");
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.problem?.detail ?? "Sign-in failed. Check your details and try again."
          : "Sign-in failed. Check your details and try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageContainer className="max-w-lg">
      <PageHeader
        description={
          isRegister
            ? "Create an account to own the matches you organize."
            : "Sign in to manage your matches and account."
        }
        eyebrow="Account"
        title={isRegister ? "Create account" : "Sign in"}
      />
      <Card className="mt-6 sm:mt-8">
        {error ? (
          <div className="mb-4">
            <ErrorState compact message={error} title="Authentication failed" />
          </div>
        ) : null}
        <form className="space-y-4" onSubmit={submit}>
          <Field htmlFor="email" label="Email">
            <Input
              autoComplete="email"
              id="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </Field>
          <Field
            error={password && password.length < 8 ? "Minimum 8 characters." : undefined}
            htmlFor="password"
            label="Password"
          >
            <Input
              autoComplete={isRegister ? "new-password" : "current-password"}
              id="password"
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </Field>
          <Button fullWidth loading={loading} type="submit">
            {isRegister ? "Create account" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-slate-600">
          {isRegister ? "Already have an account?" : "Need an account?"}{" "}
          <Link
            className="font-semibold text-brand-700 hover:text-brand-900"
            href={isRegister ? "/login" : "/register"}
          >
            {isRegister ? "Sign in" : "Register"}
          </Link>
        </p>
      </Card>
    </PageContainer>
  );
}
