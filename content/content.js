console.log("FillMate AI is running!");

// Test profile
const profile = {
    firstName: "Rahul",
    lastName: "Kumar",
    email: "rahul@example.com",
    phone: "9876543210",
    education: "B.Tech CSE",
    address: "Vijayawada"
};


// SAVE PROFILE
chrome.storage.local.set(
    { userProfile: profile },
    () => {
        console.log("Profile saved successfully!");
    }
);


// GET PROFILE
chrome.storage.local.get(
    ["userProfile"],
    (result) => {

        const savedProfile = result.userProfile;

        console.log("Saved profile:", savedProfile);

        if (!savedProfile) {
            console.log("No profile found.");
            return;
        }

        fillForm(savedProfile);
    }
);


// Find the label of a field
function getFieldLabel(field) {

    if (field.labels && field.labels.length > 0) {
        return field.labels[0].innerText.trim();
    }

    if (field.getAttribute("aria-label")) {
        return field.getAttribute("aria-label").trim();
    }

    if (field.placeholder) {
        return field.placeholder.trim();
    }

    if (field.name) {
        return field.name.trim();
    }

    if (field.id) {
        return field.id.trim();
    }

    return "";
}


// Fill form
function fillForm(profile) {

    const fields = document.querySelectorAll(
        "input, textarea, select"
    );

    fields.forEach(field => {

        const label = getFieldLabel(field).toLowerCase();
        const name = field.name.toLowerCase();
        const id = field.id.toLowerCase();


        if (
            label.includes("first name") ||
            name.includes("firstname") ||
            id.includes("firstname")
        ) {
            fillField(field, profile.firstName);
        }


        else if (
            label.includes("last name") ||
            name.includes("lastname") ||
            id.includes("lastname")
        ) {
            fillField(field, profile.lastName);
        }


        else if (
            label.includes("email") ||
            name.includes("email") ||
            id.includes("email")
        ) {
            fillField(field, profile.email);
        }


        else if (
            label.includes("phone") ||
            label.includes("mobile") ||
            name.includes("phone") ||
            name.includes("mobile")
        ) {
            fillField(field, profile.phone);
        }


        else if (
            label.includes("education") ||
            name.includes("education") ||
            id.includes("education")
        ) {
            fillField(field, profile.education);
        }


        else if (
            label.includes("address") ||
            name.includes("address") ||
            id.includes("address")
        ) {
            fillField(field, profile.address);
        }

    });

    console.log("Form filling completed!");
}


// Actually put value into field
function fillField(field, value) {

    if (!value) return;

    field.value = value;

    field.dispatchEvent(
        new Event("input", { bubbles: true })
    );

    field.dispatchEvent(
        new Event("change", { bubbles: true })
    );// Listen for profile data from the popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

    if (message.action === "fillForm") {

        console.log("Received profile from popup:");
        console.log(message.profile);

        fillForm(message.profile);

        sendResponse({
            success: true
        });
    }

});
}