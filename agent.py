import os
import subprocess
import webbrowser
from dotenv import load_dotenv

load_dotenv()

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, room_io, function_tool
from livekit.plugins import google, ai_coustics

from prompt import AGENT_INSTRUCTION, AGENT_RESPONSE


@function_tool()
async def open_app_or_site(query: str) -> str:
    """Open a website on the Ultron PC by name."""
    known_sites = {
        "youtube": "https://youtube.com",
        "gmail": "https://mail.google.com",
        "google": "https://google.com",
        "github": "https://github.com",
        "whatsapp": "https://web.whatsapp.com",
    }

    key = query.lower().strip()
    url = known_sites.get(key)

    if not url:
        if key.startswith(("http://", "https://")):
            url = key
        else:
            url = f"https://{key}.com"

    webbrowser.open(url)
    return f"Opened {query} on the Ultron PC."


@function_tool()
async def open_app_on_phone(app_name: str) -> str:
    """Open an Android app on a phone connected to this PC through ADB."""
    known_packages = {
        "youtube": "com.google.android.youtube/.HomeActivity",
        "whatsapp": "com.whatsapp/.HomeActivity",
        "instagram": "com.instagram.android/.activity.MainTabActivity",
        "gmail": "com.google.android.gm/.ConversationListActivityGmail",
        "settings": "com.android.settings/.Settings",
        "camera": "com.android.camera/.Camera",
        "chrome": "com.android.chrome/com.google.android.apps.chrome.Main",
    }

    key = app_name.lower().strip()
    package = known_packages.get(key)

    if not package:
        return f"I don't have a saved package name for {app_name} yet, Sir."

    try:
        subprocess.run(
            ["adb", "shell", "am", "start", "-n", package],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return f"Opened {app_name} on the connected Android phone."
    except subprocess.CalledProcessError:
        pkg_only = package.split("/")[0]
        subprocess.run(
            [
                "adb", "shell", "monkey", "-p", pkg_only,
                "-c", "android.intent.category.LAUNCHER", "1",
            ],
            check=False,
            capture_output=True,
            timeout=10,
        )
        return f"Opened {app_name} on the connected Android phone."


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION + "\n\n" + AGENT_RESPONSE,
            tools=[open_app_or_site, open_app_on_phone],
        )


server = AgentServer()


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: agents.JobContext):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is missing from .env")

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            api_key=api_key,
            voice="Aoede",
            temperature=0.8,
            instructions=(
                AGENT_INSTRUCTION
                + "\n\n"
                + AGENT_RESPONSE
                + "\n\n"
                + "Activation: respond when the user says 'Hey ULTRON' or 'ULTRON'. "
                  "The phone remote is an authorized control interface. "
                  "When the user asks you to open a website on the PC, call open_app_or_site. "
                  "When the user asks you to open an Android app on the ADB-connected phone, "
                  "call open_app_on_phone. Never claim an action was completed unless the tool "
                  "returns successfully."
            ),
        )
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_S
                ),
            ),
        ),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
