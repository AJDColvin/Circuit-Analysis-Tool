def is_pangram(s):
    dictionary = ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']
    appeared = []

    for letter in s:
        if letter.lower() in dictionary:
            dictionary.remove(letter.lower())

    if len(dictionary) == 0:
        return True
    else:
        return False


stringy = "The quick, brown fox jumps oer the lazy dog!"
print(is_pangram(stringy))

def comp(array1, array2):
    # your code
    if len(array1) > 0 and len(array2) > 0:
        correctarray2 = []
        for num in array1:
            correctarray2.append(num*num)

        array2copy = array2.copy()
        array2copy.sort()
        correctarray2.sort()

        if array2copy == correctarray2:
            return True
        else:
            return False
	
    else:
        return False