import { createRoot } from "react-dom/client";
import App from "./App";
import { api, MOCK } from "./api";
import "./styles.css";

createRoot(document.getElementById("root")!).render(<App api={api} mock={MOCK} />);
