import { redirect } from "next/navigation";

// 入口頁直接導到 /dashboard,middleware 會把未登入用戶再導到 /login
export default function Home() {
  redirect("/dashboard");
}
