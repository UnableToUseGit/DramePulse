import { StatusBar } from "expo-status-bar";
import { PlayerScreen } from "./src/screens/PlayerScreen";

export default function App() {
  return (
    <>
      <StatusBar style="light" hidden />
      <PlayerScreen />
    </>
  );
}
