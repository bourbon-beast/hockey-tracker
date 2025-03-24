// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
    apiKey: "AIzaSyDncOm08locgxANdkL6JZpp1kSTm-5gGxs",
    authDomain: "hockey-tracker-e67d0.firebaseapp.com",
    projectId: "hockey-tracker-e67d0",
    storageBucket: "hockey-tracker-e67d0.firebasestorage.app",
    messagingSenderId: "78172159693",
    appId: "1:78172159693:web:967172bca6b18c5f787384",
    measurementId: "G-4JLGV7PR5J"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);