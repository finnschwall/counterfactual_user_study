const roomName = "room1"
let ws_scheme = window.location.protocol == "https:" ? "wss://" : "ws://";
const websocketURL =  ws_scheme + window.location.host+ '/ws/chat/'+ roomName+'/'

let reconnectTries = 0
const maxTries =3
let chatSocket

let lastUsedId=0
let messageHistory = []

let lastUsedDisplay = 0


initializeWebSocket()

$("#userInput").prop("disabled",true)
const toastJS= bootstrap.Toast.getOrCreateInstance($("#liveToast"))
let timeout_id = -1
// showMessage("Connecting to server..", timeout = 2000)



function showMessage(message, timeout=5000, theme="info"){
    $("#toast_text").html(message)
    $("#toast_title").text(theme.charAt(0).toUpperCase() + theme.slice(1))
    for(let i in ["danger","info", "success", "warning"]){
        $("#toast_header_div").removeClass(`text-bg-${i}`)
        $("#liveToast").removeClass(`text-bg-${i}`);
    }
    $("#toast_header_div").addClass(`text-bg-${theme}`)
    $("#liveToast").addClass(`text-bg-${theme}`);
    const now = new Date();
const timeString = now.toLocaleTimeString("de-DE", { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    $("#toast_timestamp").html(timeString)
    toastJS.show()
    if(timeout_id !=-1){
        clearTimeout(timeout_id)
    }
    if(timeout!=-1){
        timeout_id= setTimeout(
          function()
              {
                toastJS.hide()
                  timeout_id=-1
              }, timeout);
    }


}


function initializeWebSocket() {

    if(reconnectTries>=maxTries){

        $("#server_content_displayer").html("<img src='https://http.cat/599'style='height: 100%; display: block; margin: auto'>")
        // $("#server_content_displayer").css({"background-image":`url('https://http.cat/599')`,
        //                      "background-size": "cover", "background-size": "100vw 100vh"});
        showMessage(`Server unreachable. No further connection attempts will be made.`,-1,"danger")

        // hideBotTyping()
        return
    }
    chatSocket = new WebSocket(websocketURL);
    chatSocket.onerror = onErrorHandler;
    chatSocket.onopen = onOpenHandler;
    chatSocket.onmessage = onMessageHandler;
    chatSocket.onclose = onCloseHandler;
}

function clearConversations(){
    send({"CMD":"clear_tracker"})
}

// Using a message that looks like this
// {'CMD': "function_call", "plugin_name" : "X", "function_name":"Y", "args": [A1, A2], "kwargs":{"A":"B"}}
// you can call plugin functions on the server
async function send(message) {
    chatSocket.send(JSON.stringify(message));
}


function cmd(text){
    send({'content': text, "msg_id": lastUsedId, "role": "user"})
}

function onMessageHandler(e) {

    const data = JSON.parse(e.data);
    if("role" in data){
        if(data["role"]==="status"){
            showMessage(data["content"],data["timeout"], data["level"])
        }
        else if(data["role"]==="HTML") {
            $(`#content_main_${lastUsedDisplay}`).html(data["content"])
            $(`#content_main_${lastUsedDisplay}`).show()
            lastUsedDisplay++
            lastUsedDisplay%=container_count
            hideBotTyping();
        }
        else if(data["role"]==="JSON"){
            lastUsedDisplay = 1
            // $(`#content_main_1`).hide()
            $(`#content_main_0`).jsonViewer(JSON.parse(data["content"]));
        }
        else if(data["role"]==="flag"){
            if(data["content"]=="show_bot_loading"){
                showBotTyping()
                scrollToBottomOfResults()
            }

        }
        else if(data["role"]==="variable"){
            if("datasize" in data){
                $("#datapoint_selection").prop("max", `${data["datasize"]}`)
                $("#datapoint_selection").prop("placeholder", `Max value: ${data["datasize"]}`)
            }
            else if("feature_weights" in data){
                // $("#a_range").prop("min", data["feature_weights"]["A"])

            }


        }
        else {
            lastUsedId+=1
            addMessage(data)
            hideBotTyping();
            //data["msg_id"] = lastUsedId
            //
            // setBotResponse(data)
        }
    }

    if("update_conversation" in data){
        $("#userInput").prop("disabled",false)
        lastUsedId=data["update_conversation"]["active_message_id"]
        messageHistory = data["update_conversation"]["messages"]
        let availableConvos = Object.keys(data["update_conversation"]["messages"])

        rebuildConversation()
        hideBotTyping();
    }

};

function rebuildConversation(){
      $(".chats").html(`<div class="clearfix"></div>
        <div class="statusMessage">
            <p class="statusInner" id="statusMessage" style="display: none"></p>
        </div>
        <div class="clearfix"></div>`);
    for(let i in messageHistory){
        if(messageHistory[i]["role"]!="system"){
            addMessage(messageHistory[i])
        }
    }
}


function onErrorHandler(e){
    hideBotTyping()
    reconnectTries++
    console.error(e)
}

function onOpenHandler(e){
    // showMessage("Connected successfully",5000)
    $("#userInput").prop("disabled",false)
    openChat()
}

function onCloseHandler(e) {

    if(e["code"]==1000){
        return
    }
    $("#userInput").prop("disabled",true)
    showMessage(`Connection to server lost ${reconnectTries+1} times. Retrying in 5 seconds.`, 5000, "warning")
    setTimeout(initializeWebSocket, 5000);
};


