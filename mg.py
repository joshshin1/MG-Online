from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import threading
import random
import copy

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

player_lock = threading.Lock()
players = []
players_folded = set()
namemap = {}
stackmap = {}
cardmap = {}
player_limit = 8

deck_lock = threading.Lock()
game_in_progress = False
cards_left = 52
action = 0
current_bet = 0
last_action = ''
deck = [
  '2C', '2D', '2H', '2S',
  '3C', '3D', '3H', '3S',
  '4C', '4D', '4H', '4S',
  '5C', '5D', '5H', '5S',
  '6C', '6D', '6H', '6S',
  '7C', '7D', '7H', '7S',
  '8C', '8D', '8H', '8S',
  '9C', '9D', '9H', '9S',
  '10C', '10D', '10H', '10S',
  'JC', 'JD', 'JH', 'JS',
  'QC', 'QD', 'QH', 'QS',
  'KC', 'KD', 'KH', 'KS',
  'AC', 'AD', 'AH', 'AS',
]
valuemap = {
  '2' : 2,
  '3' : 3,
  '4' : 4,
  '5' : 5,
  '6' : 6,
  '7' : 7,
  '8' : 8,
  '9' : 9,
  '1' : 10,
  'J' : 11,
  'Q' : 12,
  'K' : 13,
  'A' : 14
}

@app.route('/', methods=['POST', 'GET'])
def index():
  return render_template('play.html')

def nextHand(): 
  global game_in_progress
  global cards_left 
  global current_bet
  global last_action
  global action
  global players_folded
  game_in_progress = True
  cards_left = 52
  current_bet = 0
  last_action = ''
  players_folded = set()
  emit('update', {'id' : 'winner', 'val' : ''}, broadcast=True)
  for player in players:
    emit('highlight', {'name' : namemap[player] + 'info', 'color' : 'white', 'border' : 'grey'}, broadcast=True)
    emit('highlight', {'name' : 'control_block', 'color' : 'white', 'border' : 'white'}, broadcast=True)
    emit('update', {'id' : namemap[player] + 'bet', 'val' : '0'}, broadcast=True)
    emit('update image', {'id' : namemap[player] + 'card', 'val' : 'Red_back'}, broadcast=True)
  makeDealer(players[action])

  
def nextPlayer():
  global action
  global last_action
  if last_action != 'fold':
    emit('highlight', {'name' : namemap[players[action]] + 'info', 'color' : 'white', 'border' : 'grey'}, broadcast=True)
    emit('highlight', {'name' : 'control_block', 'color' : 'white', 'border' : 'white'})
  action = (action + 1) % len(players)
  while players[action] in players_folded:
    action = (action + 1) % len(players)
  makeDealer(players[action])


def makeDealer(player):
  emit('highlight', {'name' : namemap[player] + 'info', 'color' : 'skyblue', 'border' : 'blue'}, broadcast=True)
  emit('highlight', {'name' : 'control_block', 'color' : 'skyblue', 'border' : 'blue'}, to=player)


def showdown():
  global game_in_progress

  final_two = []
  for player in players:
    if player not in players_folded:
      final_two.append(player)

  player1 = final_two[0]
  player2 = final_two[1]

  emit('update image', {'id' : namemap[player1] + 'card', 'val' : cardmap[player1]}, broadcast=True)
  emit('update image', {'id' : namemap[player2] + 'card', 'val' : cardmap[player2]}, broadcast=True)

  if (
    valuemap[cardmap[player1][0]] < valuemap[cardmap[player2][0]]
    and not (valuemap[cardmap[player1][0]] == 2 and valuemap[cardmap[player2][0]] > 10)
    or valuemap[cardmap[player2][0]] == 2 and valuemap[cardmap[player1][0]] > 10
  ):
      transfer(player1, player2)
      emit('update', {'id' : 'winner', 'val' : namemap[player2] + ' WINS'}, broadcast=True)
  elif valuemap[cardmap[player1][0]] == valuemap[cardmap[player2][0]]:
      print('tie')
  else:
      transfer(player2, player1)
      emit('update', {'id' : 'winner', 'val' : namemap[player1] + ' WINS'}, broadcast=True)
  game_in_progress = False


def transfer(loser, winner):
  print('transfer', current_bet, 'from', loser, 'to', winner)
  stackmap[loser] -= current_bet
  stackmap[winner] += current_bet
  emit('update', {'id' : namemap[loser] + 'stack', 'val' : stackmap[loser]}, broadcast=True)
  emit('update', {'id' : namemap[winner] + 'stack', 'val' : stackmap[winner]}, broadcast=True)
  emit('update max', {'val' : stackmap[loser]}, to=loser)
  emit('update max', {'val' : stackmap[winner]}, to=winner)


@socketio.on('request card')
def dealCard(data):
  print('card requested')
  global cards_left
  deck_lock.acquire()
  card_index = random.randint(0, cards_left - 1)
  cards_left -= 1
  card = deck[card_index]
  deck[card_index] = deck[cards_left]
  deck[cards_left] = card
  deck_lock.release()
  cardmap[data['id']] = card
  emit('deal card', {'card' : card})


@socketio.on('init players')
def init_players():
  print('init')
  print(players)
  for player in players:
    emit('insert player', {'name' : namemap[player]})
  for player in players_folded:
    emit('highlight', {'name' : namemap[player] + 'info', 'color' : 'lightcoral', 'border' : 'red'})
  for player in players:
    emit('update', {'id' : namemap[player] + 'stack', 'val' : stackmap[player]})
    emit('update image', {'id' : namemap[player] + 'card', 'val' : cardmap[player]})
  if len(players) > 0:
    emit('highlight', {'name' : namemap[players[action]] + 'info', 'color' : 'skyblue', 'border' : 'blue'})


@socketio.on('reconnection')
def reconnection(data):
  print('reconnect')
  print(players)
  print(data)
  global action
  player_lock.acquire()
  for i in range(len(players)):
    if players[i] == data['old_id']:
      players[i] = data['new_id']
      break
  player_lock.release()
  namemap[data['new_id']] = namemap[data['old_id']]
  namemap.pop(data['old_id'])
  stackmap[data['new_id']] = stackmap[data['old_id']]
  stackmap.pop(data['old_id'])
  cardmap[data['new_id']] = cardmap[data['old_id']]
  cardmap.pop(data['old_id'])
  if data['old_id'] in players_folded:
    players_folded.remove(data['old_id'])
    players_folded.add(data['new_id'])
    emit('highlight', {'name' : 'control_block', 'color' : 'lightcoral', 'border' : 'red'})
  if i == action:
    emit('highlight', {'name' : 'control_block', 'color' : 'skyblue', 'border' : 'blue'})
  emit('deal card', {'card' : cardmap[data['new_id']]})


@socketio.on('play')
def sit(data):
  print('sit')
  print(players)
  print(data)
  global game_in_progress
  if data['id'] not in players and data['name'] != '' and len(players) < player_limit:
    player_lock.acquire()
    players.append(data['id'])
    player_lock.release()
    namemap[data['id']] = data['name']
    stackmap[data['id']] = int(data['stack'])
    cardmap[data['id']] = 'Red_back'
    emit('insert player', {'name' : data['name'], 'stack' : data['stack']}, broadcast=True)
    emit('update max', {'val' : stackmap[data['id']]}, to=data['id'])
    emit('successful join', {'name' : data['name']})
    if len(players) == 1:
      makeDealer(players[0])
    if game_in_progress:
      emit('highlight', {'name' : namemap[data['id']] + 'info', 'color' : 'lightcoral', 'border' : 'red'}, broadcast=True)
      emit('highlight', {'name' : 'control_block', 'color' : 'lightcoral', 'border' :'red'})
      players_folded.add(data['id'])

  elif data['id'] in players and players[action] == data['id']:
    print('dealing')
    nextHand()
    emit('start game', to='private room')


@socketio.on('leave game')
def leave(data):
  print('leave game')
  print(players)
  print(data)
  global game_in_progress
  global action
  val = namemap[data['id']]
  if data['id'] in players and game_in_progress:
    emit('warning', {'val' : 'CANNOT LEAVE DURING A HAND'})
  elif data['id'] in players and not game_in_progress:
    player_lock.acquire()
    index = 0
    for i in range(len(players)):
      if players[i] == data['id']:
        index = i
    players.remove(data['id'])
    namemap.pop(data['id'])
    stackmap.pop(data['id'])
    cardmap.pop(data['id'])
    player_lock.release()
    if index <= action and len(players) > 0:
      action = (action - 1) % len(players) 
      makeDealer(players[action])

    emit('highlight', {'name' : 'control_block', 'color' : 'white', 'border' : 'white'})
    emit('delete player', {'name' : val}, broadcast=True)
    emit('successful leave')


# fold call raise
@socketio.on('fold')
def fold(data):
  global action
  global last_action
  global game_in_progress
  if players[action] != data['id']:
    emit('warning', {'val' : 'OUT OF TURN'})
  elif not game_in_progress:
    emit('warning', {'val' : 'GAME HASNT BEEN STARTED'})
  else:
    emit('highlight', {'name' : namemap[players[action]] + 'info', 'color' : 'lightcoral', 'border' : 'red'}, broadcast=True)
    emit('highlight', {'name' : 'control_block', 'color' : 'lightcoral', 'border' : 'red'})
    players_folded.add(data['id'])
    if len(players) - len(players_folded) == 2 and last_action == 'call':
      showdown()
    # there is a winner
    elif len(players) - len(players_folded) == 1:
      #emit('highlight', {'name' : namemap[players[action]] + 'info', 'color' : 'lightcoral', 'border' : 'red'}, broadcast=True)
      #emit('highlight', {'name' : 'control_block', 'color' : 'lightcoral', 'border' : 'red'})
      game_in_progress = False
      winner = None
      for player in players:
        if player not in players_folded:
          winner = player
          break
      transfer(data['id'], winner)
      emit('update', {'id' : 'winner', 'val' : namemap[winner] + ' WINS'}, broadcast=True)
    last_action = 'fold'
    nextPlayer()


@socketio.on('call')
def call(data):
  global action
  global last_action
  global current_bet
  if players[action] != data['id']:
    emit('warning', {'val' : 'OUT OF TURN'})
  elif not game_in_progress:
    emit('warning', {'val' : 'GAME HASNT BEEN STARTED'})
  elif last_action == 'call':
    emit('warning', {'val' : 'ONLY ONE CALL IS ALLOWED'})
  elif not current_bet:
    emit('warning', {'val' : 'NO BET TO CALL'})
  elif stackmap[data['id']] < current_bet:
    emit('warning', {'val' : 'NOT ENOUGH MONEY'})
  else:
    emit('update', {'id' : namemap[data['id']] + 'bet', 'val' : current_bet}, broadcast=True)
    if len(players) - len(players_folded) == 2:
      showdown()
    else:
      emit('highlight', {'name' : namemap[players[action]] + 'info', 'color' : 'white', 'border' : 'grey'}, broadcast=True)
      last_action = 'call'
    nextPlayer()  

@socketio.on('raise') # make this a raise / bet event
def raisebet(data):
  global action
  global last_action
  global current_bet
  if players[action] != data['id']:
    emit('warning', {'val' : 'OUT OF TURN'})
  elif not game_in_progress:
    emit('warning', {'val' : 'GAME HASNT BEEN STARTED'})
  elif not data['val'].isnumeric():
    emit('warning', {'val' : 'INVALID RAISE'})
  elif int(data['val']) < current_bet:
    emit('warning', {'val' : 'RAISE/BET TOO LOW'})
  elif int(data['val']) > int(data['stack']):
    emit('warning', {'val' : 'NOT ENOUGH MONEY'})
  else:
    current_bet = int(data['val'])
    emit('highlight', {'name' : namemap[players[action]] + 'info', 'color' : 'white', 'border' : 'grey'}, broadcast=True)
    emit('update', {'id' : namemap[data['id']] + 'bet', 'val' : data['val']}, broadcast=True)
    last_action = 'raise'
    nextPlayer()


# handle joining and leaving rooms
@socketio.on('join')
def join(data):
  print('join')
  print(players)
  print(data)
  join_room(data['room'])

@socketio.on('leave')
def leave(data):
  print('leave')
  print(players)
  print(data)
  leave_room(data['room'])


if __name__ == '__main__':
  socketio.run(app)#, host='0.0.0.0')