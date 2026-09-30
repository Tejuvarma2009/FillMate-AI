const fillMode = document.getElementById("fillMode");
const summaryMode = document.getElementById("summaryMode");

const heading = document.getElementById("heading");
const userInput = document.getElementById("userInput");

const fillButton = document.getElementById("fillButton");
const buttonText = document.getElementById("buttonText");

const micButton = document.getElementById("micButton");


let currentMode = "fill";


/* =========================
   FILL FORMS MODE
========================= */

fillMode.addEventListener("click", () => {

    currentMode = "fill";

    fillMode.classList.add("active");
    summaryMode.classList.remove("active");

    heading.innerHTML = `
        What can I help<br>
        you with?
    `;

    userInput.placeholder =
        "Tell me what you need to fill...";

    buttonText.textContent =
        "Analyze form";
});


/* =========================
   SUMMARIZE MODE
========================= */

summaryMode.addEventListener("click", () => {

    currentMode = "summary";

    summaryMode.classList.add("active");
    fillMode.classList.remove("active");

    heading.innerHTML = `
        Understand your<br>
        documents faster.
    `;

    userInput.placeholder =
        "Ask something about this document...";

    buttonText.textContent =
        "Summarize document";
});


/* =========================
   MAIN BUTTON
========================= */

fillButton.addEventListener("click", async () => {

    /* =====================
       FILL FORM
    ===================== */

    if (currentMode === "fill") {

        buttonText.textContent = "Analyzing...";

        fillButton.disabled = true;


        try {

            const [tab] = await chrome.tabs.query({
                active: true,
                currentWindow: true
            });


            if (!tab || !tab.id) {

                console.log("No active tab found.");

                buttonText.textContent =
                    "Analyze form";

                fillButton.disabled = false;

                return;
            }


            /*
             * This keeps your existing
             * content-script connection.
             */

            chrome.tabs.sendMessage(
                tab.id,

                {
                    action: "fillForm",

                    profile: {

                        firstName: "Rahul",

                        lastName: "Kumar",

                        email: "rahul@example.com",

                        phone: "9876543210",

                        education: "B.Tech CSE",

                        address: "Vijayawada"

                    }
                },

                (response) => {

                    if (chrome.runtime.lastError) {

                        console.log(
                            "Content script error:",
                            chrome.runtime.lastError.message
                        );

                        buttonText.textContent =
                            "Open a form page";

                        setTimeout(() => {

                            buttonText.textContent =
                                "Analyze form";

                            fillButton.disabled = false;

                        }, 1500);

                        return;
                    }


                    console.log(
                        "Response from content script:",
                        response
                    );


                    buttonText.textContent =
                        "Form analyzed";


                    setTimeout(() => {

                        buttonText.textContent =
                            "Analyze form";

                        fillButton.disabled = false;

                    }, 1200);

                }
            );

        }

        catch (error) {

            console.error(error);

            buttonText.textContent =
                "Something went wrong";

            setTimeout(() => {

                buttonText.textContent =
                    "Analyze form";

                fillButton.disabled = false;

            }, 1500);

        }

    }


    /* =====================
       SUMMARIZE
    ===================== */

    else if (currentMode === "summary") {

        buttonText.textContent =
            "Coming soon...";

        fillButton.disabled = true;


        /*
         * We will connect PDF/document
         * summarization here next.
         */


        setTimeout(() => {

            buttonText.textContent =
                "Summarize document";

            fillButton.disabled = false;

        }, 1200);

    }

});


/* =========================
   MICROPHONE
========================= */

const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;


let recognition = null;


if (SpeechRecognition) {

    recognition = new SpeechRecognition();

    recognition.continuous = false;

    recognition.interimResults = false;

    recognition.lang = "en-IN";


    recognition.onstart = () => {

        micButton.classList.add("listening");

    };


    recognition.onresult = (event) => {

        const transcript =
            event.results[0][0].transcript;


        if (userInput.value.trim()) {

            userInput.value +=
                " " + transcript;

        }
        else {

            userInput.value =
                transcript;

        }

    };


    recognition.onend = () => {

        micButton.classList.remove("listening");

    };


    recognition.onerror = (event) => {

        console.log(
            "Microphone error:",
            event.error
        );

        micButton.classList.remove("listening");

    };


    micButton.addEventListener("click", () => {

        try {

            recognition.start();

        }
        catch (error) {

            console.log(error);

        }

    });

}
else {

    micButton.addEventListener("click", () => {

        console.log(
            "Speech recognition is not supported."
        );

    });

}