import json

def get_data():
    with open('data.json', 'r') as file:
        return json.load(file)

def main():
    data = get_data()
    print(data)

if __name__ == '__main__':
    main()